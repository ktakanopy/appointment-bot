from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.application.contracts.workflow_dtos import WorkflowAppointmentSnapshot


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
    def is_appointment_mutation(self) -> bool:
        return self in {
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


class ResponseKey(str, Enum):
    COLLECT_FULL_NAME = "collect_full_name"
    COLLECT_PHONE = "collect_phone"
    COLLECT_DOB = "collect_dob"
    INVALID_FULL_NAME = "invalid_full_name"
    INVALID_PHONE = "invalid_phone"
    INVALID_DOB = "invalid_dob"
    VERIFICATION_FAILED = "verification_failed"
    VERIFICATION_LOCKED = "verification_locked"
    HELP_VERIFIED = "help_verified"
    HELP_UNVERIFIED = "help_unverified"
    APPOINTMENTS_LIST = "appointments_list"
    CONFIRM_SUCCESS = "confirm_success"
    CONFIRM_ALREADY_CONFIRMED = "confirm_already_confirmed"
    CONFIRM_NOT_ALLOWED = "confirm_not_allowed"
    CANCEL_SUCCESS = "cancel_success"
    CANCEL_ALREADY_CANCELED = "cancel_already_canceled"
    CANCEL_NOT_ALLOWED = "cancel_not_allowed"
    APPOINTMENT_NOT_OWNED = "appointment_not_owned"
    APPOINTMENT_NOT_FOUND = "appointment_not_found"
    CONFIRM_MISSING_LIST_CONTEXT = "confirm_missing_list_context"
    CANCEL_MISSING_LIST_CONTEXT = "cancel_missing_list_context"
    CONFIRM_AMBIGUOUS_REFERENCE = "confirm_ambiguous_reference"
    CANCEL_AMBIGUOUS_REFERENCE = "cancel_ambiguous_reference"


class ConversationOperationOutcome(str, Enum):
    LISTED = "listed"
    CONFIRMED = "confirmed"
    ALREADY_CONFIRMED = "already_confirmed"
    CANCELED = "canceled"
    ALREADY_CANCELED = "already_canceled"


class ConversationOperationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    operation: ConversationOperation
    outcome: ConversationOperationOutcome
    appointment_id: str | None = None


class VerificationSnapshot(BaseModel):
    verified: bool = False
    status: VerificationStatus = VerificationStatus.UNVERIFIED
    failures: int = 0
    patient_id: str | None = None
    provided_full_name: str | None = None
    provided_phone: str | None = None
    provided_dob: str | None = None


class TurnSnapshot(BaseModel):
    requested_operation: ConversationOperation = ConversationOperation.UNKNOWN
    deferred_operation: ConversationOperation | None = None
    response_key: ResponseKey | None = None
    issue: TurnIssue | None = None
    operation_result: ConversationOperationResult | None = None
    subject_appointment: WorkflowAppointmentSnapshot | None = None


class ConversationWorkflowInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    thread_id: str
    incoming_message: str


class ConversationWorkflowResult(BaseModel):
    thread_id: str
    verification: VerificationSnapshot = Field(default_factory=VerificationSnapshot)
    turn: TurnSnapshot = Field(default_factory=TurnSnapshot)
    listed_appointments: list[WorkflowAppointmentSnapshot] = Field(default_factory=list)
    appointment_reference: str | None = None
