from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AppointmentStatus(str, Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    CANCELED = "canceled"


class ActionOutcome(str, Enum):
    LISTED = "listed"
    CONFIRMED = "confirmed"
    ALREADY_CONFIRMED = "already_confirmed"
    CANCELED = "canceled"
    ALREADY_CANCELED = "already_canceled"


class ConversationOperation(str, Enum):
    VERIFY_IDENTITY = "verify_identity"
    LIST_APPOINTMENTS = "list_appointments"
    CONFIRM_APPOINTMENT = "confirm_appointment"
    CANCEL_APPOINTMENT = "cancel_appointment"
    HELP = "help"
    UNKNOWN = "unknown"

    @property
    def requires_verification(self) -> bool:
        return self in {
            ConversationOperation.LIST_APPOINTMENTS,
            ConversationOperation.CONFIRM_APPOINTMENT,
            ConversationOperation.CANCEL_APPOINTMENT,
        }

    @property
    def triggers_verification_flow(self) -> bool:
        return self in {
            ConversationOperation.HELP,
            ConversationOperation.UNKNOWN,
            ConversationOperation.VERIFY_IDENTITY,
        }


class VerificationStatus(str, Enum):
    UNVERIFIED = "unverified"
    COLLECTING = "collecting"
    FAILED = "failed"
    VERIFIED = "verified"
    LOCKED = "locked"


class TurnIssue(str, Enum):
    INVALID_FULL_NAME = "invalid_full_name"
    INVALID_PHONE = "invalid_phone"
    INVALID_DOB = "invalid_dob"
    INVALID_IDENTITY = "invalid_identity"
    VERIFICATION_LOCKED = "verification_locked"
    MISSING_LIST_CONTEXT = "missing_list_context"
    AMBIGUOUS_APPOINTMENT_REFERENCE = "ambiguous_appointment_reference"
    APPOINTMENT_NOT_CONFIRMABLE = "appointment_not_confirmable"
    APPOINTMENT_NOT_CANCELABLE = "appointment_not_cancelable"
    APPOINTMENT_NOT_OWNED = "appointment_not_owned"
    APPOINTMENT_NOT_FOUND = "appointment_not_found"


class DomainError(Exception):
    pass


class AppointmentNotConfirmableError(DomainError):
    pass


class AppointmentNotCancelableError(DomainError):
    pass


class AppointmentNotOwnedError(DomainError):
    pass


class AppointmentNotFoundError(DomainError):
    pass


class ApplicationError(Exception):
    pass


class SessionNotFoundError(ApplicationError):
    pass


class DependencyUnavailableError(ApplicationError):
    pass


class FullName(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: str

    @classmethod
    def try_parse(cls, raw: str | None) -> str | None:
        if not raw:
            return None
        try:
            return cls(raw).value
        except ValueError:
            return None

    def __init__(self, raw: str):
        super().__init__(value=raw)

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str) -> str:
        normalized = " ".join(part for part in value.strip().split())
        if len(normalized.split()) < 2:
            raise ValueError("full name requires first and last name")
        return normalized.title()

    def __str__(self) -> str:
        return self.value


class Phone(BaseModel):
    model_config = ConfigDict(frozen=True)

    digits: str

    @classmethod
    def try_parse(cls, raw: str | None) -> str | None:
        if not raw:
            return None
        try:
            return cls(raw).digits
        except ValueError:
            return None

    def __init__(self, raw: str):
        super().__init__(digits=raw)

    @field_validator("digits")
    @classmethod
    def validate_digits(cls, value: str) -> str:
        digits = "".join(character for character in value if character.isdigit())
        if len(digits) < 10:
            raise ValueError("phone requires at least 10 digits")
        return digits

    def __str__(self) -> str:
        return self.digits


class DateOfBirth(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: str

    @classmethod
    def try_parse(cls, raw: str | None) -> str | None:
        if not raw:
            return None
        try:
            return cls(raw).value
        except ValueError:
            return None

    def __init__(self, raw: str):
        super().__init__(value=raw)

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str) -> str:
        cleaned = value.strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(cleaned, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        raise ValueError("date of birth must use YYYY-MM-DD or DD/MM/YYYY")

    def __str__(self) -> str:
        return self.value


class Patient(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    full_name: FullName
    phone: Phone
    date_of_birth: DateOfBirth


class Appointment(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    patient_id: str
    date: str
    time: str
    doctor: str
    status: AppointmentStatus

    def confirm(self) -> tuple[Appointment, ActionOutcome]:
        if self.status == AppointmentStatus.CONFIRMED:
            return self, ActionOutcome.ALREADY_CONFIRMED
        if self.status != AppointmentStatus.SCHEDULED:
            raise AppointmentNotConfirmableError(self.id)
        return self.model_copy(update={"status": AppointmentStatus.CONFIRMED}), ActionOutcome.CONFIRMED

    def cancel(self) -> tuple[Appointment, ActionOutcome]:
        if self.status == AppointmentStatus.CANCELED:
            return self, ActionOutcome.ALREADY_CANCELED
        if self.status not in {AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED}:
            raise AppointmentNotCancelableError(self.id)
        return self.model_copy(update={"status": AppointmentStatus.CANCELED}), ActionOutcome.CANCELED

    def is_owned_by(self, patient_id: str | None) -> bool:
        return bool(patient_id and self.patient_id == patient_id)

    @property
    def is_confirmable(self) -> bool:
        return self.status == AppointmentStatus.SCHEDULED

    @property
    def is_cancelable(self) -> bool:
        return self.status in {AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED}


class SessionRecord(BaseModel):
    session_id: str
    thread_id: str
    created_at: float
    last_seen_at: float


class ConversationOperationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    operation: ConversationOperation
    outcome: ActionOutcome
    appointment_id: str | None = None


class ChatTurnResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response: str
    verified: bool
    current_operation: ConversationOperation
    thread_id: str
    appointments: list[dict[str, object]] | None = None
    last_action_result: ConversationOperationResult | None = None
    issue: str | None = None


class NewSessionResponseData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    thread_id: str
    response: str | None = None


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    session_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=4000)


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
