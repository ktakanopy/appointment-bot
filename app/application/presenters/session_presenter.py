from __future__ import annotations

from app.application.contracts.public import NewSessionResponseData
from app.application.contracts.session import SessionRecord


class SessionPresenter:
    def present(self, session: SessionRecord) -> NewSessionResponseData:
        return NewSessionResponseData(
            session_id=session.session_id,
            thread_id=session.thread_id,
            response="Hello, I'm CAPY. I can help you with your appointments.",
        )
