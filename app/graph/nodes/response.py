from __future__ import annotations

from app.application.contracts.conversation import ConversationOperation, ResponseKey
from app.graph.state import ConversationState, turn_state, verification_state
from app.observability import log_event


def make_help_node(logger):
    def help_or_unknown(state: ConversationState) -> ConversationState:
        verification = verification_state(state)
        turn = turn_state(state)
        turn.requested_operation = ConversationOperation.HELP
        if verification.verified:
            turn.response_key = ResponseKey.HELP_VERIFIED
        else:
            turn.response_key = ResponseKey.HELP_UNVERIFIED
        log_event(logger, "handle_help_or_unknown", state)
        return state

    return help_or_unknown
