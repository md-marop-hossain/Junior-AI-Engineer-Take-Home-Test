"""LangGraph construction for the StayEase booking agent."""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from .nodes import (
    call_tool,
    classify_intent,
    compose_response,
    escalate_to_human,
    route_intent,
)
from .state import AgentState


def build_graph() -> "CompiledGraph":  # type: ignore[name-defined]
    """Wire nodes and edges into the compiled StayEase graph.

    Flow:
        START -> classify_intent
                    -> (tool intents)     call_tool -> compose_response -> END
                    -> (anything else)    escalate_to_human            -> END
    """
    builder: StateGraph = StateGraph(AgentState)

    builder.add_node("classify_intent", classify_intent)
    builder.add_node("call_tool", call_tool)
    builder.add_node("compose_response", compose_response)
    builder.add_node("escalate_to_human", escalate_to_human)

    builder.add_edge(START, "classify_intent")
    builder.add_conditional_edges(
        "classify_intent",
        route_intent,
        {
            "call_tool": "call_tool",
            "escalate_to_human": "escalate_to_human",
        },
    )
    builder.add_edge("call_tool", "compose_response")
    builder.add_edge("compose_response", END)
    builder.add_edge("escalate_to_human", END)

    return builder.compile()


# Module-level singleton for the FastAPI layer to import.
graph = build_graph()
