from __future__ import annotations

from typing import TypedDict

from app.action_names import ActionName
from app.domain.models import Appointment


class ConversationState(TypedDict, total=False):
    thread_id: str
    incoming_message: str
    messages: list[dict[str, str]]
    verified: bool
    verification_status: str | None
    patient_id: str | None
    provided_full_name: str | None
    provided_phone: str | None
    provided_dob: str | None
    missing_verification_fields: list[str]
    requested_action: ActionName | None
    deferred_action: ActionName | None
    listed_appointments: list[Appointment]
    appointment_reference: str | None
    selected_appointment_id: str | None
    last_action_result: dict[str, str | None] | None
    response_text: str | None
    error_code: str | None
    provider_error: str | None
    remembered_identity_id: str | None
    remembered_identity_status: dict[str, str | None] | None


def ensure_state_defaults(state: ConversationState) -> ConversationState:
    state.setdefault("messages", [])
    state.setdefault("verified", False)
    state.setdefault("verification_status", None)
    state.setdefault("patient_id", None)
    state.setdefault("provided_full_name", None)
    state.setdefault("provided_phone", None)
    state.setdefault("provided_dob", None)
    state.setdefault("missing_verification_fields", [])
    state.setdefault("requested_action", "unknown")
    state.setdefault("deferred_action", None)
    state.setdefault("listed_appointments", [])
    state.setdefault("appointment_reference", None)
    state.setdefault("selected_appointment_id", None)
    state.setdefault("last_action_result", None)
    state.setdefault("response_text", None)
    state.setdefault("error_code", None)
    state.setdefault("provider_error", None)
    state.setdefault("remembered_identity_id", None)
    state.setdefault("remembered_identity_status", None)
    return state
