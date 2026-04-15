from __future__ import annotations

from app.application.presenters.chat_presenter import ChatPresenter
from app.application.presenters.session_presenter import SessionPresenter
from app.runtime_assembly.bundles import PresenterBundle


def build_presenters() -> PresenterBundle:
    session_presenter = SessionPresenter()
    chat_presenter = ChatPresenter()
    return PresenterBundle(
        session_presenter=session_presenter,
        chat_presenter=chat_presenter,
    )
