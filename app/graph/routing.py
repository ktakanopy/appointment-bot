from __future__ import annotations

from app.domain.actions import Action
from app.graph.state import ConversationState

def verification_required(state: ConversationState) -> bool:
    action = state.turn.requested_action
    return bool(
        not state.verification.verified
        and (
            action is not None
            and (action.requires_verification or action.triggers_verification_flow)
            or state.turn.deferred_action
        )
    )


def should_skip_action_execution(state: ConversationState) -> bool:
    return bool(state.turn.response_text)


def route_after_interpret(state: ConversationState) -> str:
    if verification_required(state):
        return "verify"
    return "execute_action"


def route_after_verify(state: ConversationState) -> str:
    if should_skip_action_execution(state):
        return "generate_response"
    return "execute_action"
