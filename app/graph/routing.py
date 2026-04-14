from __future__ import annotations

from app.domain.policies import PROTECTED_ACTIONS

VERIFICATION_FIRST_ACTIONS = {"help", "unknown", "verify_identity"}


def verification_required(state: dict) -> bool:
    action = state.get("turn", {}).get("requested_action")
    return bool(
        not state.get("verification", {}).get("verified")
        and (
            action in PROTECTED_ACTIONS
            or action in VERIFICATION_FIRST_ACTIONS
            or state.get("turn", {}).get("deferred_action")
        )
    )


def should_skip_action_execution(state: dict) -> bool:
    return bool(state.get("turn", {}).get("response_text"))
