from __future__ import annotations

from typing import TypedDict

from app.action_names import ActionName
from app.domain.models import Appointment


class ConversationState(TypedDict, total=False):
    thread_id: str
    incoming_message: str
    messages: list[dict[str, str]]
    verified: bool
    verification_failures: int
    verification_status: str | None
    patient_id: str | None
    provided_full_name: str | None
    provided_phone: str | None
    provided_dob: str | None
    requested_action: ActionName | None
    deferred_action: ActionName | None
    listed_appointments: list[Appointment]
    appointment_reference: str | None
    last_action_result: dict[str, str | None] | None
    response_text: str | None
    error_code: str | None


def ensure_state_defaults(state: ConversationState) -> ConversationState:
    """Initialize the persisted graph state expected by downstream nodes."""
    state.setdefault("messages", [])
    state.setdefault("verified", False)
    state.setdefault("verification_failures", 0)
    state.setdefault("verification_status", None)
    state.setdefault("patient_id", None)
    state.setdefault("provided_full_name", None)
    state.setdefault("provided_phone", None)
    state.setdefault("provided_dob", None)
    state.setdefault("requested_action", "unknown")
    state.setdefault("deferred_action", None)
    state.setdefault("listed_appointments", [])
    state.setdefault("appointment_reference", None)
    state.setdefault("last_action_result", None)
    state.setdefault("response_text", None)
    state.setdefault("error_code", None)
    return state
