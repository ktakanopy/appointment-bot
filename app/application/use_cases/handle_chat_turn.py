from __future__ import annotations

from app.application.contracts.conversation import ConversationWorkflowInput
from app.application.contracts.public import ChatTurnResponse
from app.application.presenters.chat_presenter import ChatPresenter
from app.application.services.chat_response_service import ChatResponseService
from app.application.session_service import SessionService
from app.application.ports.workflow_runner import ConversationWorkflow


class HandleChatTurnUseCase:
    def __init__(
        self,
        session_service: SessionService,
        workflow: ConversationWorkflow,
        chat_response_service: ChatResponseService,
        chat_presenter: ChatPresenter,
    ):
        self.session_service = session_service
        self.workflow = workflow
        self.chat_response_service = chat_response_service
        self.chat_presenter = chat_presenter

    def execute(
        self,
        *,
        session_id: str,
        message: str,
    ) -> ChatTurnResponse:
        self.session_service.cleanup_expired()
        session = self.session_service.require_session(session_id)
        workflow_result = self.workflow.run(
            ConversationWorkflowInput(
                thread_id=session.thread_id,
                incoming_message=message,
            )
        )
        response_text = self.chat_response_service.generate(workflow_result)
        return self.chat_presenter.present(
            thread_id=session.thread_id,
            response_text=response_text,
            workflow_result=workflow_result,
        )
