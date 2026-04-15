from __future__ import annotations

from dataclasses import dataclass

from app.application.ports.checkpoint_store import CheckpointStore
from app.application.ports.session_store import SessionStore
from app.application.ports.workflow_runner import ConversationWorkflow
from app.application.presenters.chat_presenter import ChatPresenter
from app.application.presenters.session_presenter import SessionPresenter
from app.application.services.chat_response_service import ChatResponseService
from app.application.session_service import SessionService
from app.application.use_cases.create_session import CreateSessionUseCase
from app.application.use_cases.handle_chat_turn import HandleChatTurnUseCase
from app.domain.ports import AppointmentRepository, PatientRepository
from app.domain.services import AppointmentService, VerificationService
from app.llm.base import LLMProvider


@dataclass(frozen=True)
class RepositoryBundle:
    patient_repository: PatientRepository
    appointment_repository: AppointmentRepository
    session_store: SessionStore
    checkpoint_store: CheckpointStore


@dataclass(frozen=True)
class ServiceBundle:
    provider: LLMProvider
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
    graph: object
    workflow: ConversationWorkflow


@dataclass(frozen=True)
class UseCaseBundle:
    create_session_use_case: CreateSessionUseCase
    handle_chat_turn_use_case: HandleChatTurnUseCase
