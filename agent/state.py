"""Shared LangGraph state for the StayEase assistant."""
from __future__ import annotations

from typing import Annotated, Literal, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


Intent = Literal["search", "details", "book", "escalate", "unknown"]


class SearchCriteria(TypedDict, total=False):
    """Search details extracted from a guest message."""

    location: str
    check_in: str   # ISO date "YYYY-MM-DD"
    check_out: str  # ISO date "YYYY-MM-DD"
    guests: int


class AgentState(TypedDict):
    """Shared state passed between every node in the graph."""

    conversation_id: str
    # Full conversation transcript. `add_messages` appends new turns safely.
    messages: Annotated[list[BaseMessage], add_messages]
    # Detected guest intent used by the router.
    intent: Intent
    # Parsed search fields (location, dates, guests).
    search_criteria: SearchCriteria
    # Listing currently referenced by the guest (details/booking flows).
    listing_id: Optional[str]
    # Raw payload returned by the latest tool.
    tool_result: Optional[dict]
    # Final assistant reply for the current turn.
    response: Optional[str]
    # True when the chat should be handed off to a human.
    escalate: bool
    # Guest contact details carried from API input into booking steps.
    guest_name: Optional[str]
    guest_phone: Optional[str]
