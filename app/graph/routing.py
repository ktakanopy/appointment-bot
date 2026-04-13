from __future__ import annotations

from app.domain.policies import PROTECTED_ACTIONS


def route_after_interpret(state: dict) -> str:
    action = state.get("requested_action")
    if not state.get("verified") and (action in PROTECTED_ACTIONS or state.get("deferred_action")):
        return "verification_subgraph"
    if action == "list_appointments":
        return "list_appointments"
    if action == "confirm_appointment":
        return "confirm_appointment"
    if action == "cancel_appointment":
        return "cancel_appointment"
    return "handle_help_or_unknown"


def route_after_verification(state: dict) -> str:
    if state.get("response_text") and not state.get("verified"):
        return "generate_response"

    action = state.get("requested_action")
    if action == "list_appointments":
        return "list_appointments"
    if action == "confirm_appointment":
        return "confirm_appointment"
    if action == "cancel_appointment":
        return "cancel_appointment"
    return "handle_help_or_unknown"
