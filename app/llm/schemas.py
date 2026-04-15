from __future__ import annotations

from typing import Literal

from pydantic import AliasChoices, BaseModel, Field

from app.models import ConversationOperation


class IntentPrediction(BaseModel):
    requested_operation: ConversationOperation = Field(
        default=ConversationOperation.UNKNOWN,
        validation_alias=AliasChoices("requested_operation", "requested_action"),
        serialization_alias="requested_operation",
    )
    full_name: str | None = None
    phone: str | None = None
    dob: str | None = None
    appointment_reference: str | None = None


class JudgeResult(BaseModel):
    status: Literal["pass", "fail", "error"]
    summary: str
    score: float | None = None
