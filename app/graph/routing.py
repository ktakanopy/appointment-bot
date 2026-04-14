from __future__ import annotations

from app.domain.policies import PROTECTED_ACTIONS
from app.graph.state import ConversationState

VERIFICATION_FIRST_ACTIONS = {"help", "unknown", "verify_identity"}


def verification_required(state: ConversationState) -> bool:
    action = state.turn.requested_action
    return bool(
        not state.verification.verified
        and (
            action in PROTECTED_ACTIONS
            or action in VERIFICATION_FIRST_ACTIONS
            or state.turn.deferred_action
        )
    )


def should_skip_action_execution(state: ConversationState) -> bool:
    return bool(state.turn.response_text)
