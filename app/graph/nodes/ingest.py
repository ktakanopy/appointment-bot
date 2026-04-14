from __future__ import annotations

from app.graph.state import ConversationState, ensure_state_defaults
from app.observability import log_event


def make_ingest_node(logger):
    def ingest(state: ConversationState) -> ConversationState:
        """Normalize the incoming turn and prepare state for downstream nodes.

        This node ensures the graph state has all expected default keys before
        any other node reads from it. It trims the raw incoming message, clears
        transient per-turn output fields from the previous step such as
        `error_code`, `response_text`, and `last_action_result`, and appends the
        current user message to the conversation history when the message is not
        empty. The resulting state becomes the clean starting point for intent
        parsing, verification, and action handling in the rest of the workflow.
        """
        state = ensure_state_defaults(state)
        message = (state.get("incoming_message") or "").strip()
        state["error_code"] = None
        state["response_text"] = None
        state["last_action_result"] = None
        if message:
            state["messages"].append({"role": "user", "content": message})
        log_event(logger, "ingest_user_message", state)
        return state

    return ingest
