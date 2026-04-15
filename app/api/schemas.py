from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.application.contracts.public import (
    AppointmentSummary,
    ChatTurnResponse,
    NewSessionResponseData,
)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    session_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=4000)


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str


ChatResponse = ChatTurnResponse
NewSessionResponse = NewSessionResponseData
