from __future__ import annotations

from app.graph.state import ConversationState


def verification_required(state: ConversationState) -> bool:
    operation = state.turn.requested_operation
    return bool(
        not state.verification.verified
        and (
            operation.requires_verification
            or operation.triggers_verification_flow
            or state.turn.deferred_operation
        )
    )


def should_skip_action_execution(state: ConversationState) -> bool:
    return state.turn.has_turn_output()


def route_after_interpret(state: ConversationState) -> str:
    if verification_required(state):
        return "verify"
    return "execute_action"


def route_after_verify(state: ConversationState) -> str:
    if should_skip_action_execution(state):
        return "end"
    return "execute_action"
