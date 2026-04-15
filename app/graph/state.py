from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.action_names import ActionName
from app.domain.models import Appointment


class StateModel(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, validate_assignment=True)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def __setitem__(self, key: str, value: Any) -> None:
        setattr(self, key, value)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return getattr(self, key)
        except AttributeError:
            return default

    def setdefault(self, key: str, default: Any = None) -> Any:
        value = getattr(self, key, None)
        if value is None:
            setattr(self, key, default)
        return getattr(self, key)


class VerificationState(StateModel):
    verified: bool = False
    verification_failures: int = 0
    verification_status: Optional[str] = None
    patient_id: Optional[str] = None
    provided_full_name: Optional[str] = None
    provided_phone: Optional[str] = None
    provided_dob: Optional[str] = None

    def mark_collecting(self) -> None:
        self.verification_status = "collecting"

    def mark_verified(self, patient_id: str) -> None:
        self.verification_status = "verified"
        self.verified = True
        self.verification_failures = 0
        self.patient_id = patient_id

    def reset_failed_verification(self) -> None:
        self.verification_status = "failed"
        self.verified = False
        self.patient_id = None
        self.provided_full_name = None
        self.provided_phone = None
        self.provided_dob = None

    def fill_missing_fields(
        self,
        *,
        full_name: Optional[str],
        phone: Optional[str],
        dob: Optional[str],
    ) -> None:
        if self.provided_full_name is None and full_name:
            self.provided_full_name = full_name
        if self.provided_phone is None and phone:
            self.provided_phone = phone
        if self.provided_dob is None and dob:
            self.provided_dob = dob

    def missing_fields(self) -> list[str]:
        missing = []
        if not self.provided_full_name:
            missing.append("full_name")
        if not self.provided_phone:
            missing.append("phone")
        if not self.provided_dob:
            missing.append("dob")
        return missing

    def next_missing_field(self) -> Optional[str]:
        missing = self.missing_fields()
        if not missing:
            return None
        return missing[0]


class TurnState(StateModel):
    requested_action: Optional[ActionName] = None
    deferred_action: Optional[ActionName] = None
    last_action_result: Optional[dict[str, Optional[str]]] = None
    response_text: Optional[str] = None
    error_code: Optional[str] = None

    def resume_deferred_action(self) -> None:
        if self.deferred_action:
            self.requested_action = self.deferred_action
            self.deferred_action = None

    def clear_transient_output(self) -> None:
        self.error_code = None
        self.response_text = None
        self.last_action_result = None


class AppointmentState(StateModel):
    listed_appointments: list[Appointment] = Field(default_factory=list)
    appointment_reference: Optional[str] = None


class ConversationState(StateModel):
    thread_id: str = ""
    incoming_message: str = ""
    messages: list[dict[str, str]] = Field(default_factory=list)
    verification: VerificationState = Field(default_factory=VerificationState)
    turn: TurnState = Field(default_factory=TurnState)
    appointments: AppointmentState = Field(default_factory=AppointmentState)

    def add_user_message(self, content: str) -> None:
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str) -> None:
        self.messages.append({"role": "assistant", "content": content})


def verification_state(state: ConversationState) -> VerificationState:
    return state.verification


def turn_state(state: ConversationState) -> TurnState:
    return state.turn


def appointment_state(state: ConversationState) -> AppointmentState:
    return state.appointments
