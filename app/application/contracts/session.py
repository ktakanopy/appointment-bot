from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.application.contracts.conversation import WorkflowVerificationBootstrap


class SessionBootstrap(BaseModel):
    model_config = ConfigDict(frozen=True)

    verification: WorkflowVerificationBootstrap | None = None
    created_at: float


class SessionRecord(BaseModel):
    session_id: str
    thread_id: str
    created_at: float
    last_seen_at: float
    remembered_identity_id: str | None = None
    bootstrap: SessionBootstrap | None = None
