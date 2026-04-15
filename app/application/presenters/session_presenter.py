from __future__ import annotations

from app.application.contracts.public import NewSessionResponseData
from app.application.contracts.session import SessionRecord
from app.domain.models import RememberedIdentity, RememberedIdentityStatus

from .identity_presenter import IdentityPresenter


class SessionPresenter:
    def __init__(self, identity_presenter: IdentityPresenter):
        self.identity_presenter = identity_presenter

    def present(
        self,
        session: SessionRecord,
        restored_identity: RememberedIdentity | None,
        requested_identity_id: str | None = None,
    ) -> NewSessionResponseData:
        restored_verification = bool(
            restored_identity is not None and restored_identity.status == RememberedIdentityStatus.ACTIVE
        )
        if restored_verification:
            response = f"Welcome back, {restored_identity.display_name or 'patient'}. I'm CAPY, and your identity has been restored."
        else:
            response = "Hello, I'm CAPY. I can help you with your appointments."
        return NewSessionResponseData(
            session_id=session.session_id,
            thread_id=session.thread_id,
            restored_verification=restored_verification,
            remembered_identity_status=self.identity_presenter.present(restored_identity, requested_identity_id),
            response=response,
        )
