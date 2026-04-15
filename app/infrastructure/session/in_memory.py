from __future__ import annotations

from app.application.contracts.session import SessionRecord


class InMemorySessionStore:
    def __init__(self):
        self._sessions: dict[str, SessionRecord] = {}

    def get(self, session_id: str) -> SessionRecord | None:
        return self._sessions.get(session_id)

    def save(self, session: SessionRecord) -> SessionRecord:
        self._sessions[session.session_id] = session
        return session

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def list(self) -> list[SessionRecord]:
        return list(self._sessions.values())
