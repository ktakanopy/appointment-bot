from __future__ import annotations

import time
from uuid import uuid4

from app.application.contracts.conversation import WorkflowVerificationBootstrap
from app.application.contracts.session import SessionBootstrap, SessionRecord
from app.application.errors import SessionNotFoundError
from app.application.ports.session_store import SessionStore
from app.domain.models import RememberedIdentity, RememberedIdentityStatus

SESSION_BOOTSTRAP_TTL_SECONDS = 300


class SessionService:
    def __init__(
        self,
        session_store: SessionStore,
        session_ttl_minutes: int,
        bootstrap_ttl_seconds: int = SESSION_BOOTSTRAP_TTL_SECONDS,
    ):
        self.session_store = session_store
        self.session_ttl_seconds = session_ttl_minutes * 60
        self.bootstrap_ttl_seconds = bootstrap_ttl_seconds

    def create_session(self) -> SessionRecord:
        session_id = str(uuid4())
        now = time.monotonic()
        session = SessionRecord(
            session_id=session_id,
            thread_id=session_id,
            created_at=now,
            last_seen_at=now,
        )
        return self.session_store.save(session)

    def cleanup_expired(self) -> None:
        now = time.monotonic()
        for session in self.session_store.list():
            updated = session
            if session.bootstrap and now - session.bootstrap.created_at > self.bootstrap_ttl_seconds:
                updated = updated.model_copy(update={"bootstrap": None})
            if now - updated.last_seen_at > self.session_ttl_seconds:
                self.session_store.delete(updated.session_id)
                continue
            if updated != session:
                self.session_store.save(updated)

    def require_session(self, session_id: str) -> SessionRecord:
        session = self.session_store.get(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        updated = session.model_copy(update={"last_seen_at": time.monotonic()})
        return self.session_store.save(updated)

    def save_session(self, session: SessionRecord) -> SessionRecord:
        return self.session_store.save(session)

    def build_bootstrap(self, identity: RememberedIdentity | None, created_at: float | None = None) -> SessionBootstrap | None:
        if identity is None or identity.status != RememberedIdentityStatus.ACTIVE:
            return None
        return SessionBootstrap(
            verification=WorkflowVerificationBootstrap(patient_id=identity.patient_id),
            created_at=created_at if created_at is not None else time.monotonic(),
        )
