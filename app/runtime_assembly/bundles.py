from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.application.presenters.chat_presenter import ChatPresenter
from app.application.presenters.session_presenter import SessionPresenter
from app.application.services.chat_response_service import ChatResponseService
from app.application.session_service import SessionService
from app.application.use_cases.create_session import CreateSessionUseCase
from app.application.use_cases.handle_chat_turn import HandleChatTurnUseCase
from app.domain.services import AppointmentService, VerificationService


@dataclass(frozen=True)
class RepositoryBundle:
    patient_repository: Any
    appointment_repository: Any
    session_store: Any
    checkpoint_store: Any


@dataclass(frozen=True)
class ServiceBundle:
    provider: Any
    verification_service: VerificationService
    appointment_service: AppointmentService
    session_service: SessionService
    response_service: ChatResponseService


@dataclass(frozen=True)
class PresenterBundle:
    session_presenter: SessionPresenter
    chat_presenter: ChatPresenter


@dataclass(frozen=True)
class WorkflowBundle:
    graph: Any
    workflow: Any


@dataclass(frozen=True)
class UseCaseBundle:
    create_session_use_case: CreateSessionUseCase
    handle_chat_turn_use_case: HandleChatTurnUseCase
