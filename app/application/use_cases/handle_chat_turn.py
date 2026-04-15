from __future__ import annotations

from app.application.contracts.conversation import ConversationWorkflowInput
from app.application.contracts.public import ChatTurnResponse
from app.application.presenters.chat_presenter import ChatPresenter
from app.application.presenters.identity_presenter import IdentityPresenter
from app.application.session_service import SessionService
from app.application.ports.workflow_runner import ConversationWorkflow
from app.domain.services import RememberedIdentityService


class HandleChatTurnUseCase:
    def __init__(
        self,
        session_service: SessionService,
        identity_service: RememberedIdentityService,
        workflow: ConversationWorkflow,
        chat_presenter: ChatPresenter,
        identity_presenter: IdentityPresenter,
    ):
        self.session_service = session_service
        self.identity_service = identity_service
        self.workflow = workflow
        self.chat_presenter = chat_presenter
        self.identity_presenter = identity_presenter

    def execute(
        self,
        *,
        session_id: str,
        message: str,
        remembered_identity_id: str | None = None,
    ) -> ChatTurnResponse:
        self.session_service.cleanup_expired()
        session = self.session_service.require_session(session_id)
        if remembered_identity_id:
            session = session.model_copy(update={"remembered_identity_id": remembered_identity_id})
        bootstrap = session.bootstrap
        session = session.model_copy(update={"bootstrap": None})
        if bootstrap is None and remembered_identity_id:
            restored_identity = self.identity_service.restore_identity(remembered_identity_id)
            bootstrap = self.session_service.build_bootstrap(restored_identity)
        workflow_result = self.workflow.run(
            ConversationWorkflowInput(
                thread_id=session.thread_id,
                incoming_message=message,
                bootstrap_verification=bootstrap.verification if bootstrap is not None else None,
            )
        )
        remembered_identity = self._ensure_remembered_identity(
            session=session,
            requested_identity_id=remembered_identity_id,
            workflow_result=workflow_result,
        )
        session = session.model_copy(
            update={
                "remembered_identity_id": (
                    remembered_identity.remembered_identity_id
                    if remembered_identity is not None
                    else session.remembered_identity_id
                ),
                "bootstrap": None,
            }
        )
        self.session_service.save_session(session)
        remembered_identity_status = self.identity_presenter.present(
            remembered_identity,
            remembered_identity_id or session.remembered_identity_id,
        )
        return self.chat_presenter.present(
            thread_id=session.thread_id,
            workflow_result=workflow_result,
            remembered_identity_status=remembered_identity_status,
        )

    def _ensure_remembered_identity(
        self,
        *,
        session,
        requested_identity_id: str | None,
        workflow_result,
    ):
        verification = workflow_result.verification
        if not verification.verified or not verification.patient_id:
            identity_id = requested_identity_id or session.remembered_identity_id
            return self.identity_service.restore_identity(identity_id)
        fingerprint = self.identity_service.build_fingerprint(
            verification.provided_full_name,
            verification.provided_phone,
            verification.provided_dob,
            verification.patient_id,
        )
        return self.identity_service.ensure_identity(
            patient_id=verification.patient_id,
            display_name=verification.provided_full_name,
            verification_fingerprint=fingerprint,
        )
