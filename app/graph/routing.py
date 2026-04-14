from __future__ import annotations

from app.domain.policies import PROTECTED_ACTIONS

VERIFICATION_FIRST_ACTIONS = {"help", "unknown", "verify_identity"}


def verification_required(state: dict) -> bool:
    """Return whether the current turn must pass through identity verification."""
    action = state.get("requested_action")
    return bool(
        not state.get("verified")
        and (
            action in PROTECTED_ACTIONS
            or action in VERIFICATION_FIRST_ACTIONS
            or state.get("deferred_action")
        )
    )


def should_skip_action_execution(state: dict) -> bool:
    """Return whether a prior node already produced the user-facing response."""
    return bool(state.get("response_text"))
