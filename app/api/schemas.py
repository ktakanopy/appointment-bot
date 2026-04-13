from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


ActionName = Literal[
    "verify_identity",
    "list_appointments",
    "confirm_appointment",
    "cancel_appointment",
    "help",
    "unknown",
]


class ChatRequest(BaseModel):
    session_id: str
    message: str


class AppointmentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    date: str
    time: str
    doctor: str
    status: str


class ActionResultResponse(BaseModel):
    action: str
    outcome: str
    appointment_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    verified: bool
    current_action: ActionName
    thread_id: str
    appointments: list[AppointmentSummary] | None = None
    last_action_result: ActionResultResponse | None = None
    error_code: str | None = None
