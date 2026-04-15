from __future__ import annotations

from app.application.use_cases.create_session import CreateSessionUseCase
from app.application.use_cases.forget_remembered_identity import ForgetRememberedIdentityUseCase
from app.application.use_cases.handle_chat_turn import HandleChatTurnUseCase
from app.runtime_assembly.bundles import PresenterBundle, ServiceBundle, UseCaseBundle, WorkflowBundle


def build_use_cases(
    *,
    services: ServiceBundle,
    workflow_bundle: WorkflowBundle,
    presenters: PresenterBundle,
) -> UseCaseBundle:
    create_session_use_case = CreateSessionUseCase(
        session_service=services.session_service,
        identity_service=services.identity_service,
        presenter=presenters.session_presenter,
    )
    handle_chat_turn_use_case = HandleChatTurnUseCase(
        session_service=services.session_service,
        identity_service=services.identity_service,
        workflow=workflow_bundle.workflow,
        chat_response_service=services.response_service,
        chat_presenter=presenters.chat_presenter,
        identity_presenter=presenters.identity_presenter,
    )
    forget_remembered_identity_use_case = ForgetRememberedIdentityUseCase(services.identity_service)
    return UseCaseBundle(
        create_session_use_case=create_session_use_case,
        handle_chat_turn_use_case=handle_chat_turn_use_case,
        forget_remembered_identity_use_case=forget_remembered_identity_use_case,
    )
