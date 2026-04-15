from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.application.contracts.conversation import ConversationOperation


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    message: str
    remembered_identity_id: str | None = None


class AppointmentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    date: str
    time: str
    doctor: str
    status: str


class OperationResultResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: ConversationOperation
    outcome: str
    appointment_id: str | None = None


class RememberedIdentitySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    remembered_identity_id: str
    status: Literal["active", "expired", "revoked", "unavailable"]
    display_name: str | None = None
    expires_at: str | None = None


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response: str
    verified: bool
    current_operation: ConversationOperation
    thread_id: str
    appointments: list[AppointmentSummary] | None = None
    last_action_result: OperationResultResponse | None = None
    issue: str | None = None
    remembered_identity_status: RememberedIdentitySummary


class NewSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    remembered_identity_id: str | None = None


class NewSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    thread_id: str
    restored_verification: bool
    remembered_identity_status: RememberedIdentitySummary
    response: str | None = None


class ForgetRememberedIdentityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    remembered_identity_id: str


class ForgetRememberedIdentityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cleared: bool
