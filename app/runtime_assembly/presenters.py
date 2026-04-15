from __future__ import annotations

from app.application.presenters.chat_presenter import ChatPresenter
from app.application.presenters.identity_presenter import IdentityPresenter
from app.application.presenters.session_presenter import SessionPresenter
from app.runtime_assembly.bundles import PresenterBundle


def build_presenters() -> PresenterBundle:
    identity_presenter = IdentityPresenter()
    session_presenter = SessionPresenter(identity_presenter)
    chat_presenter = ChatPresenter()
    return PresenterBundle(
        identity_presenter=identity_presenter,
        session_presenter=session_presenter,
        chat_presenter=chat_presenter,
    )
