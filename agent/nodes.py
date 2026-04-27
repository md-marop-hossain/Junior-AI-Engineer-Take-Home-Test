"""LangGraph node functions for the StayEase assistant.

Each node reads the current `AgentState` and returns only the fields it wants
to update. LangGraph merges that partial output back into state.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import date
from typing import Literal, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from pydantic import BaseModel

from .config import settings
from .state import AgentState, Intent, SearchCriteria
from .tools import ALL_TOOLS


# LLM setup

def _llm() -> ChatGroq:
    """Create the chat model instance.

    Keeping this as a function makes it easy to stub in tests.
    """
    return ChatGroq(
        model=settings.groq_model,
        api_key=settings.groq_api_key or None,
        temperature=0,
    )


def _valid_uuid(v: str | None) -> bool:
    """Return True only if `v` is a parseable UUID string."""
    try:
        _uuid.UUID(str(v))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


SYSTEM_PROMPT = (
    "You are the StayEase booking assistant for short-term rentals in Bangladesh. "
    "You can ONLY help with: searching properties, showing listing details, and "
    "creating bookings. For anything else, politely escalate to a human. "
    "All prices are in BDT (Bangladeshi Taka, symbol ৳)."
)


# Structured schemas for intent parsing

class _SearchCriteriaSchema(BaseModel):
    """Search slots extracted from the guest message.

    All fields stay optional because users often provide details gradually.
    """

    location: Optional[str] = None
    check_in: Optional[str] = None   # YYYY-MM-DD
    check_out: Optional[str] = None  # YYYY-MM-DD
    guests: Optional[int] = None


class _IntentSchema(BaseModel):
    """Expected structured output from the intent classification step."""

    intent: Intent
    search_criteria: Optional[_SearchCriteriaSchema] = None
    listing_id: Optional[str] = None
    guest_name: Optional[str] = None


# Graph nodes

def classify_intent(state: AgentState) -> dict:
    """Classify the latest guest message and extract usable slots.

    Updates: `intent`, `search_criteria`, `listing_id`, `guest_name`, `escalate`.
    Next: `route_intent` (conditional edge).
    """
    last = state["messages"][-1]
    text = last.content if isinstance(last.content, str) else str(last.content)
    today = date.today().isoformat()

    llm = _llm().with_structured_output(_IntentSchema)
    parsed: _IntentSchema = llm.invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"Today is {today}. "
                    "Classify the guest message into one of: "
                    "search, details, book, escalate, unknown. "
                    "Extract slots: location, check_in (YYYY-MM-DD), "
                    "check_out (YYYY-MM-DD), guests, listing_id, guest_name. "
                    "Resolve relative dates ('tonight', 'for 2 nights', 'this weekend') "
                    "against today's date. Leave a slot null if it is not mentioned.\n\n"
                    f"Message: {text}"
                )
            ),
        ]
    )

    # Convert the parsed schema into the plain state dict, skipping null values.
    raw = parsed.search_criteria
    criteria: SearchCriteria = {}
    if raw:
        if raw.location:
            criteria["location"] = raw.location
        if raw.check_in:
            criteria["check_in"] = raw.check_in
        if raw.check_out:
            criteria["check_out"] = raw.check_out
        if raw.guests is not None:
            criteria["guests"] = raw.guests

    extracted_lid = parsed.listing_id
    final_lid = extracted_lid if _valid_uuid(extracted_lid) else state.get("listing_id")

    return {
        "intent": parsed.intent,
        "search_criteria": criteria,
        "listing_id": final_lid,
        "guest_name": parsed.guest_name or state.get("guest_name"),
        "escalate": parsed.intent in ("escalate", "unknown"),
    }


def call_tool(state: AgentState) -> dict:
    """Run the tool that matches the detected intent.

    Updates: `tool_result`.
    Next: `compose_response`.
    """
    intent: Intent = state["intent"]
    tools_by_name = {t.name: t for t in ALL_TOOLS}

    if intent == "search":
        criteria = state["search_criteria"]
        missing = [f for f in ("location", "check_in", "check_out", "guests") if not criteria.get(f)]
        if missing:
            return {"tool_result": {"error": f"Missing required information: {', '.join(missing)}"}}
        tool = tools_by_name["search_available_properties"]
        result = tool.invoke(criteria)

    elif intent == "details":
        if not state.get("listing_id"):
            return {"tool_result": {"error": "Please specify which listing you'd like details about."}}
        tool = tools_by_name["get_listing_details"]
        result = tool.invoke({"listing_id": state["listing_id"]})

    elif intent == "book":
        if not state.get("listing_id"):
            return {"tool_result": {"error": "Please specify which listing you'd like to book."}}
        tool = tools_by_name["create_booking"]
        result = tool.invoke(
            {
                "listing_id": state["listing_id"],
                "guest_name": state.get("guest_name") or "Guest",
                "guest_phone": state.get("guest_phone") or "",
                "conversation_id": state["conversation_id"],
                **state["search_criteria"],
            }
        )
    else:
        result = {"error": f"no tool for intent {intent!r}"}

    return {"tool_result": result}


def compose_response(state: AgentState) -> dict:
    """Convert tool output into a short, guest-friendly response.

    Updates: `messages` (appends AIMessage), `response`.
    Next: END.
    """
    llm = _llm()
    reply = llm.invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            *state["messages"],
            HumanMessage(
                content=(
                    "Tool result (JSON):\n"
                    f"{state['tool_result']}\n\n"
                    "Write a friendly reply to the guest in 1–3 short sentences. "
                    "Use ৳ for prices. If there are no results, say so."
                )
            ),
        ]
    )
    text = reply.content if isinstance(reply.content, str) else str(reply.content)
    return {
        "messages": [AIMessage(content=text)],
        "response": text,
    }


def escalate_to_human(state: AgentState) -> dict:
    """Hand the conversation over to a human teammate.

    Updates: `messages`, `response`, `escalate`.
    Next: END.
    """
    text = (
        "I can only help with searching, viewing, or booking StayEase properties. "
        "Let me connect you with a human teammate — they will reply shortly."
    )
    return {
        "messages": [AIMessage(content=text)],
        "response": text,
        "escalate": True,
    }


# Routing

def route_intent(state: AgentState) -> Literal["call_tool", "escalate_to_human"]:
    """Route supported intents to tools; escalate everything else."""
    if state["intent"] in ("search", "details", "book"):
        return "call_tool"
    return "escalate_to_human"
