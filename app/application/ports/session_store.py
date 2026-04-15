from __future__ import annotations

from typing import Protocol

from app.application.contracts.session import SessionRecord


class SessionStore(Protocol):
    def get(self, session_id: str) -> SessionRecord | None:
        ...

    def save(self, session: SessionRecord) -> SessionRecord:
        ...

    def delete(self, session_id: str) -> None:
        ...

    def list(self) -> list[SessionRecord]:
        ...
