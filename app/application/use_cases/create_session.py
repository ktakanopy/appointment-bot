from __future__ import annotations

from app.application.contracts.public import NewSessionResponseData
from app.application.presenters.session_presenter import SessionPresenter
from app.application.session_service import SessionService
from app.domain.models import RememberedIdentityStatus
from app.domain.services import RememberedIdentityService


class CreateSessionUseCase:
    def __init__(
        self,
        session_service: SessionService,
        identity_service: RememberedIdentityService,
        presenter: SessionPresenter,
    ):
        self.session_service = session_service
        self.identity_service = identity_service
        self.presenter = presenter

    def execute(self, remembered_identity_id: str | None = None) -> NewSessionResponseData:
        self.session_service.cleanup_expired()
        session = self.session_service.create_session()
        restored_identity = self.identity_service.restore_identity(remembered_identity_id)
        updated_session = session.model_copy(
            update={
                "remembered_identity_id": (
                    restored_identity.remembered_identity_id if restored_identity is not None else remembered_identity_id
                ),
                "bootstrap": (
                    self.session_service.build_bootstrap(restored_identity, created_at=session.created_at)
                    if restored_identity is not None and restored_identity.status == RememberedIdentityStatus.ACTIVE
                    else None
                ),
            }
        )
        self.session_service.save_session(updated_session)
        return self.presenter.present(updated_session, restored_identity, remembered_identity_id)
