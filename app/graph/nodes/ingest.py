from __future__ import annotations

from app.graph.state import ConversationState, turn_state
from app.observability import log_event


def make_ingest_node(logger):
    def ingest(state: ConversationState) -> ConversationState:
        turn = turn_state(state)
        message = (state.incoming_message or "").strip()
        turn.error_code = None
        turn.response_text = None
        turn.last_action_result = None
        if message:
            state.messages.append({"role": "user", "content": message})
        log_event(logger, "ingest_user_message", state)
        return state

    return ingest
