from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.application.contracts.conversation import ConversationOperation, ConversationOperationResult


class AppointmentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    date: str
    time: str
    doctor: str
    status: str


class ChatTurnResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response: str
    verified: bool
    current_operation: ConversationOperation
    thread_id: str
    appointments: list[AppointmentSummary] | None = None
    last_action_result: ConversationOperationResult | None = None
    issue: str | None = None


class NewSessionResponseData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    thread_id: str
    response: str | None = None
