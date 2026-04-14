from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


ActionName = Literal[
    "verify_identity",
    "list_appointments",
    "confirm_appointment",
    "cancel_appointment",
    "help",
    "unknown",
]


class IntentPrediction(BaseModel):
    requested_action: ActionName = "unknown"
    full_name: str | None = None
    phone: str | None = None
    dob: str | None = None
    appointment_reference: str | None = None


class AssistantResponse(BaseModel):
    response_text: str


class JudgeResult(BaseModel):
    status: Literal["pass", "fail", "error"]
    summary: str
    score: float | None = None
