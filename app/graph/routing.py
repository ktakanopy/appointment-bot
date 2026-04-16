from __future__ import annotations

from app.graph.state import ConversationGraphState, TurnState as TurnStateModel, turn_state, verification_state


def verification_required(state: ConversationGraphState) -> bool:
    operation = turn_state(state)["requested_operation"]
    verification = verification_state(state)
    return bool(
        not verification["verified"]
        and (
            operation.requires_verification
            or operation.triggers_verification_flow
        )
    )


def should_skip_action_execution(state: ConversationGraphState) -> bool:
    return TurnStateModel.model_validate(turn_state(state)).has_turn_output()
