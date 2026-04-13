from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.graph.state import ConversationState
from app.graph.nodes.verification import make_verification_node


def build_verification_subgraph(verification_service, logger):
    builder = StateGraph(ConversationState)
    builder.add_node("verify_identity", make_verification_node(verification_service, logger))
    builder.add_edge(START, "verify_identity")
    builder.add_edge("verify_identity", END)
    return builder.compile()
