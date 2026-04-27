"""FastAPI entry point for the StayEase booking assistant."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field

from agent.graph import graph
from db.database import init_db, seed_db, get_session
from db.models import Conversation


# Startup hooks

@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    init_db()
    seed_db()
    yield


app = FastAPI(title="StayEase Booking Agent API", version="0.1.0", lifespan=lifespan)


# Request and response models

class ChatMessageIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    guest_phone: str | None = None


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class PostMessageOut(BaseModel):
    conversation_id: UUID
    response: str
    intent: Literal["search", "details", "book", "escalate", "unknown"]
    escalated: bool
    tool_result: dict | None
    created_at: datetime


class HistoryOut(BaseModel):
    conversation_id: UUID
    escalated: bool
    messages: list[ChatMessage]
    next_before: datetime | None


# Helper functions

def _to_lc_messages(stored: list[dict]):
    """Convert stored message dictionaries to LangChain message objects."""
    out = []
    for m in stored:
        if m["role"] == "user":
            out.append(HumanMessage(content=m["content"]))
        else:
            out.append(AIMessage(content=m["content"]))
    return out


# API endpoints

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/chat/{conversation_id}/message", response_model=PostMessageOut)
def post_message(conversation_id: UUID, payload: ChatMessageIn) -> PostMessageOut:
    """Append a user turn, run the LangGraph agent, and return the reply."""
    with get_session() as session:
        # Fetch the conversation if it exists; otherwise create it.
        conv = session.get(Conversation, conversation_id)
        if conv is None:
            conv = Conversation(
                conversation_id=conversation_id,
                guest_phone=payload.guest_phone,
                messages=[],
                escalated=False,
            )
            session.add(conv)
            session.flush()

        # Build the initial agent state from saved history plus the new message.
        # Carry forward resolved slots so follow-up turns can reuse them.
        persisted = conv.agent_state or {}
        history = _to_lc_messages(conv.messages)
        initial_state: dict[str, Any] = {
            "conversation_id": str(conversation_id),
            "messages": history + [HumanMessage(content=payload.message)],
            "intent": "unknown",
            "search_criteria": persisted.get("search_criteria") or {},
            "listing_id": persisted.get("listing_id"),
            "tool_result": None,
            "response": None,
            "escalate": False,
            "guest_name": None,
            "guest_phone": payload.guest_phone or conv.guest_phone,
        }

        # Run the compiled LangGraph workflow.
        final_state: dict[str, Any] = graph.invoke(initial_state)

        response_text: str = final_state.get("response") or ""
        escalated: bool = bool(final_state.get("escalate", False))
        now = datetime.now(UTC)

        # Save both turns and refresh persisted state used across turns.
        new_messages = list(conv.messages) + [
            {"role": "user", "content": payload.message, "created_at": now.isoformat()},
            {"role": "assistant", "content": response_text, "created_at": now.isoformat()},
        ]
        conv.messages = new_messages
        conv.escalated = escalated
        # Keep the latest listing and search criteria so the next message
        # (for example, "book it") can continue the same flow.
        new_agent_state = dict(conv.agent_state or {})
        if final_state.get("listing_id"):
            new_agent_state["listing_id"] = final_state["listing_id"]
        if final_state.get("search_criteria"):
            new_agent_state["search_criteria"] = final_state["search_criteria"]
        conv.agent_state = new_agent_state

    return PostMessageOut(
        conversation_id=conversation_id,
        response=response_text,
        intent=final_state.get("intent", "unknown"),
        escalated=escalated,
        tool_result=final_state.get("tool_result"),
        created_at=now,
    )


@app.get("/api/chat/{conversation_id}/history", response_model=HistoryOut)
def get_history(
    conversation_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    before: datetime | None = None,
) -> HistoryOut:
    """Return conversation history in ascending time order."""
    with get_session() as session:
        conv = session.get(Conversation, conversation_id)
        if conv is None:
            raise HTTPException(status_code=404, detail="conversation_not_found")

        # Read required fields before leaving the session context.
        messages = [
            ChatMessage(
                role=m["role"],
                content=m["content"],
                created_at=datetime.fromisoformat(m["created_at"]),
            )
            for m in (conv.messages or [])
        ]
        escalated = conv.escalated

    if before is not None:
        messages = [m for m in messages if m.created_at < before]

    page = messages[-limit:]
    next_before = page[0].created_at if len(messages) > limit else None

    return HistoryOut(
        conversation_id=conversation_id,
        escalated=escalated,
        messages=page,
        next_before=next_before,
    )
