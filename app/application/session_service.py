from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict

from app.config import Settings
from app.domain.models import RememberedIdentity, RememberedIdentityStatus
from app.domain.services import RememberedIdentityService

SESSION_BOOTSTRAP_TTL_SECONDS = 300


class SessionNotFoundError(Exception):
    pass


class SessionBootstrap(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    state: dict[str, Any]
    created_at: float


class SessionRecord(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    session_id: str
    thread_id: str
    created_at: float
    last_seen_at: float
    remembered_identity_id: str | None = None
    bootstrap: SessionBootstrap | None = None


class SessionService:
    def __init__(self, settings: Settings, identity_service: RememberedIdentityService):
        self.settings = settings
        self.identity_service = identity_service
        self.sessions: dict[str, SessionRecord] = {}

    def create_session(self, remembered_identity_id: str | None = None) -> dict[str, Any]:
        self.cleanup_expired()
        session_id = str(uuid4())
        now = time.monotonic()
        session = SessionRecord(
            session_id=session_id,
            thread_id=session_id,
            created_at=now,
            last_seen_at=now,
        )
        self.sessions[session_id] = session
        restored_identity = self.identity_service.restore_identity(remembered_identity_id)
        session.remembered_identity_id = (
            restored_identity.remembered_identity_id if restored_identity is not None else remembered_identity_id
        )
        restored_verification = bool(
            restored_identity is not None and restored_identity.status == RememberedIdentityStatus.ACTIVE
        )
        if restored_verification:
            session.bootstrap = SessionBootstrap(
                state=self.build_bootstrap_state(restored_identity),
                created_at=now,
            )
            response = f"Welcome back, {restored_identity.display_name or 'patient'}. I'm CAPY, and your identity has been restored."
        else:
            response = "Hello, I'm CAPY. I can help you with your appointments."
        return {
            "session_id": session_id,
            "thread_id": session_id,
            "restored_verification": restored_verification,
            "remembered_identity_status": self.build_identity_summary(
                restored_identity,
                remembered_identity_id,
            ),
            "response": response,
        }

    def cleanup_expired(self) -> None:
        now = time.monotonic()
        for session in self.sessions.values():
            if session.bootstrap and now - session.bootstrap.created_at > SESSION_BOOTSTRAP_TTL_SECONDS:
                session.bootstrap = None
        ttl_seconds = self.settings.session_ttl_minutes * 60
        expired = [
            session_id
            for session_id, session in self.sessions.items()
            if now - session.last_seen_at > ttl_seconds
        ]
        for session_id in expired:
            del self.sessions[session_id]

    def require_session(self, session_id: str) -> SessionRecord:
        session = self.sessions.get(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        session.last_seen_at = time.monotonic()
        return session

    def build_bootstrap_state(self, identity: RememberedIdentity | None) -> dict[str, Any]:
        if identity is None or identity.status != RememberedIdentityStatus.ACTIVE:
            return {}
        return {
            "verification": {
                "verified": True,
                "verification_status": "verified",
                "patient_id": identity.patient_id,
            }
        }

    def build_identity_summary(
        self,
        identity: RememberedIdentity | None,
        requested_identity_id: str | None = None,
    ) -> dict[str, str | None]:
        if identity is None:
            return {
                "remembered_identity_id": requested_identity_id or "",
                "status": RememberedIdentityStatus.UNAVAILABLE.value,
                "display_name": None,
                "expires_at": None,
            }
        return self.identity_service.summary_for_identity(identity)
