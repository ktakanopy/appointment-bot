from __future__ import annotations

from typing import TypedDict

from app.action_names import ActionName
from app.domain.models import Appointment


class VerificationState(TypedDict, total=False):
    verified: bool
    verification_failures: int
    verification_status: str | None
    patient_id: str | None
    provided_full_name: str | None
    provided_phone: str | None
    provided_dob: str | None


class TurnState(TypedDict, total=False):
    requested_action: ActionName | None
    deferred_action: ActionName | None
    last_action_result: dict[str, str | None] | None
    response_text: str | None
    error_code: str | None


class AppointmentState(TypedDict, total=False):
    listed_appointments: list[Appointment]
    appointment_reference: str | None


class ConversationState(TypedDict, total=False):
    thread_id: str
    incoming_message: str
    messages: list[dict[str, str]]
    verification: VerificationState
    turn: TurnState
    appointments: AppointmentState


def ensure_state_defaults(state: ConversationState) -> ConversationState:
    state.setdefault("messages", [])
    state.setdefault("verification", {})
    state.setdefault("turn", {})
    state.setdefault("appointments", {})
    state["verification"].setdefault("verified", False)
    state["verification"].setdefault("verification_failures", 0)
    state["verification"].setdefault("verification_status", None)
    state["verification"].setdefault("patient_id", None)
    state["verification"].setdefault("provided_full_name", None)
    state["verification"].setdefault("provided_phone", None)
    state["verification"].setdefault("provided_dob", None)
    state["turn"].setdefault("requested_action", "unknown")
    state["turn"].setdefault("deferred_action", None)
    state["turn"].setdefault("last_action_result", None)
    state["turn"].setdefault("response_text", None)
    state["turn"].setdefault("error_code", None)
    state["appointments"].setdefault("listed_appointments", [])
    state["appointments"].setdefault("appointment_reference", None)
    return state


def verification_state(state: ConversationState) -> VerificationState:
    return state["verification"]


def turn_state(state: ConversationState) -> TurnState:
    return state["turn"]


def appointment_state(state: ConversationState) -> AppointmentState:
    return state["appointments"]
