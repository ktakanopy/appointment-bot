from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.application.contracts.conversation import (
    ConversationOperation,
    ConversationOperationResult,
    ResponseKey,
    TurnIssue,
    VerificationStatus,
)
from app.domain.models import Appointment


class StateModel(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, validate_assignment=True)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def __setitem__(self, key: str, value: Any) -> None:
        setattr(self, key, value)


class VerificationState(StateModel):
    verified: bool = False
    verification_failures: int = 0
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    patient_id: str | None = None
    provided_full_name: str | None = None
    provided_phone: str | None = None
    provided_dob: str | None = None

    def mark_collecting(self) -> None:
        self.verification_status = VerificationStatus.COLLECTING

    def mark_verified(self, patient_id: str) -> None:
        self.verification_status = VerificationStatus.VERIFIED
        self.verified = True
        self.verification_failures = 0
        self.patient_id = patient_id

    def reset_failed_verification(self) -> None:
        self.verification_status = VerificationStatus.FAILED
        self.verified = False
        self.patient_id = None
        self.provided_full_name = None
        self.provided_phone = None
        self.provided_dob = None

    def fill_missing_fields(
        self,
        *,
        full_name: str | None,
        phone: str | None,
        dob: str | None,
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

    def next_missing_field(self) -> str | None:
        missing = self.missing_fields()
        if not missing:
            return None
        return missing[0]


class TurnState(StateModel):
    requested_operation: ConversationOperation = ConversationOperation.UNKNOWN
    deferred_operation: ConversationOperation | None = None
    operation_result: ConversationOperationResult | None = None
    response_key: ResponseKey | None = None
    issue: TurnIssue | None = None
    subject_appointment: Appointment | None = None

    def resume_deferred_operation(self) -> None:
        if self.deferred_operation:
            self.requested_operation = self.deferred_operation
            self.deferred_operation = None

    def reset_turn_output(self) -> None:
        self.response_key = None
        self.issue = None
        self.operation_result = None
        self.subject_appointment = None

    def has_turn_output(self) -> bool:
        return any(
            value is not None
            for value in (
                self.response_key,
                self.issue,
                self.operation_result,
                self.subject_appointment,
            )
        )


class AppointmentState(StateModel):
    listed_appointments: list[Appointment] = Field(default_factory=list)
    appointment_reference: str | None = None


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

    def recent_messages(self, limit: int) -> list[dict[str, str]]:
        if limit <= 0:
            return []
        return self.messages[-limit:]


def verification_state(state: ConversationState) -> VerificationState:
    return state.verification


def turn_state(state: ConversationState) -> TurnState:
    return state.turn


def appointment_state(state: ConversationState) -> AppointmentState:
    return state.appointments
