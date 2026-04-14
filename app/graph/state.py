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

    def reset_failed_verification(self) -> None:
        self.verification_status = "failed"
        self.verified = False
        self.patient_id = None
        self.provided_full_name = None
        self.provided_phone = None
        self.provided_dob = None


class TurnState(StateModel):
    requested_action: Optional[ActionName] = None
    deferred_action: Optional[ActionName] = None
    last_action_result: Optional[dict[str, Optional[str]]] = None
    response_text: Optional[str] = None
    error_code: Optional[str] = None


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


def verification_state(state: ConversationState) -> VerificationState:
    return state.verification


def turn_state(state: ConversationState) -> TurnState:
    return state.turn


def appointment_state(state: ConversationState) -> AppointmentState:
    return state.appointments
