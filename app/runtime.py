from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.application.presenters.chat_presenter import ChatPresenter
from app.application.presenters.identity_presenter import IdentityPresenter
from app.application.presenters.session_presenter import SessionPresenter
from app.application.session_service import SessionService
from app.application.use_cases.create_session import CreateSessionUseCase
from app.application.use_cases.forget_remembered_identity import ForgetRememberedIdentityUseCase
from app.application.use_cases.handle_chat_turn import HandleChatTurnUseCase
from app.config import Settings, load_settings
from app.domain.services import AppointmentService, RememberedIdentityService, VerificationService
from app.graph.builder import build_graph
from app.infrastructure.llm.factory import build_provider
from app.infrastructure.persistence.in_memory import (
    InMemoryAppointmentRepository,
    InMemoryPatientRepository,
    InMemoryRememberedIdentityRepository,
)
from app.infrastructure.session.in_memory import InMemorySessionStore
from app.infrastructure.workflow.in_memory_checkpoint import InMemoryCheckpointStore
from app.infrastructure.workflow.langgraph_runner import LangGraphConversationWorkflow
from app.llm.base import LLMProvider
from app.observability import build_tracer, get_logger


class RuntimeContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    settings: Settings
    logger: logging.Logger
    tracer: object | None
    graph: Any
    workflow: Any
    provider: Any
    identity_service: RememberedIdentityService
    session_service: SessionService
    create_session_use_case: CreateSessionUseCase
    handle_chat_turn_use_case: HandleChatTurnUseCase
    forget_remembered_identity_use_case: ForgetRememberedIdentityUseCase


def create_runtime(settings: Settings | None = None) -> RuntimeContext:
    settings = settings or load_settings()
    logger = get_logger()
    tracer = build_tracer(settings)
    provider = build_provider(settings, logger, tracer=tracer)
    patient_repository = InMemoryPatientRepository()
    appointment_repository = InMemoryAppointmentRepository()
    identity_repository = InMemoryRememberedIdentityRepository()
    session_store = InMemorySessionStore()
    checkpoint_store = InMemoryCheckpointStore()
    verification_service = VerificationService(patient_repository)
    appointment_service = AppointmentService(appointment_repository)
    identity_service = RememberedIdentityService(identity_repository, settings.remembered_identity_ttl_hours)
    session_service = SessionService(session_store, settings.session_ttl_minutes)
    graph = build_graph(
        logger=logger,
        provider=provider,
        verification_service=verification_service,
        appointment_service=appointment_service,
        max_verification_attempts=settings.max_verification_attempts,
        checkpointer=checkpoint_store.build_checkpointer(),
    )
    workflow = LangGraphConversationWorkflow(graph, logger, tracer=tracer)
    identity_presenter = IdentityPresenter()
    session_presenter = SessionPresenter(identity_presenter)
    chat_presenter = ChatPresenter(provider)
    create_session_use_case = CreateSessionUseCase(
        session_service=session_service,
        identity_service=identity_service,
        presenter=session_presenter,
    )
    handle_chat_turn_use_case = HandleChatTurnUseCase(
        session_service=session_service,
        identity_service=identity_service,
        workflow=workflow,
        chat_presenter=chat_presenter,
        identity_presenter=identity_presenter,
    )
    forget_remembered_identity_use_case = ForgetRememberedIdentityUseCase(identity_service)
    return RuntimeContext(
        settings=settings,
        logger=logger,
        tracer=tracer,
        graph=graph,
        workflow=workflow,
        provider=provider,
        identity_service=identity_service,
        session_service=session_service,
        create_session_use_case=create_session_use_case,
        handle_chat_turn_use_case=handle_chat_turn_use_case,
        forget_remembered_identity_use_case=forget_remembered_identity_use_case,
    )


def close_runtime(runtime: RuntimeContext | None) -> None:
    return None


def reset_runtime(target_app, settings: Settings | None = None) -> RuntimeContext:
    close_runtime(getattr(target_app.state, "runtime", None))
    runtime = create_runtime(settings=settings)
    target_app.state.runtime = runtime
    return runtime
