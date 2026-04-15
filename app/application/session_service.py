from __future__ import annotations

import time
from uuid import uuid4

from app.application.contracts.session import SessionRecord
from app.application.errors import SessionNotFoundError
from app.application.ports.session_store import SessionStore


class SessionService:
    def __init__(
        self,
        session_store: SessionStore,
        session_ttl_minutes: int,
    ):
        self.session_store = session_store
        self.session_ttl_seconds = session_ttl_minutes * 60

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
            if now - session.last_seen_at > self.session_ttl_seconds:
                self.session_store.delete(session.session_id)
                continue

    def require_session(self, session_id: str) -> SessionRecord:
        session = self.session_store.get(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        updated = session.model_copy(update={"last_seen_at": time.monotonic()})
        return self.session_store.save(updated)
