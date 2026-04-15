from __future__ import annotations

from app.application.contracts.public import NewSessionResponseData
from app.application.presenters.session_presenter import SessionPresenter
from app.application.session_service import SessionService


class CreateSessionUseCase:
    def __init__(
        self,
        session_service: SessionService,
        presenter: SessionPresenter,
    ):
        self.session_service = session_service
        self.presenter = presenter

    def execute(self) -> NewSessionResponseData:
        self.session_service.cleanup_expired()
        session = self.session_service.create_session()
        return self.presenter.present(session)
