from __future__ import annotations

from app.graph.state import ConversationState, turn_state
from app.observability import log_event


def make_ingest_node(logger):
    def ingest(state: ConversationState) -> ConversationState:
        turn = turn_state(state)
        message = (state.incoming_message or "").strip()
        turn.clear_transient_output()
        if message:
            state.add_user_message(message)
        log_event(logger, "ingest_user_message", state)
        return state

    return ingest
