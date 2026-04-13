from __future__ import annotations

from app.graph.state import ConversationState, ensure_state_defaults
from app.observability import log_event


def make_ingest_node(logger):
    def ingest(state: ConversationState) -> ConversationState:
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
