from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from app.config import Settings, load_settings
from app.graph.builder import build_graph
from app.graph.workflow import LangGraphWorkflow
from app.llm.provider import OpenAIProvider
from app.observability import build_tracer, get_eval_logger, get_logger
from app.repositories import InMemoryAppointmentRepository, InMemoryPatientRepository, InMemorySessionStore
from app.services import AppointmentService, SessionService, VerificationService


@dataclass
class RuntimeContext:
    settings: Settings
    logger: logging.Logger
    tracer: object | None
    checkpoint_connection: sqlite3.Connection
    graph: object
    workflow: LangGraphWorkflow
    provider: OpenAIProvider
    session_service: SessionService


def build_provider(settings: Settings, logger: logging.Logger, tracer: object | None = None) -> OpenAIProvider:
    if settings.provider.provider_name != "openai":
        raise ValueError(f"Unsupported LLM provider: {settings.provider.provider_name}")
    if not settings.provider.api_key:
        raise ValueError("OPENAI_API_KEY is required")
    return OpenAIProvider(settings.provider, logger, tracer=tracer)


def build_checkpointer(settings: Settings) -> tuple[SqliteSaver, sqlite3.Connection]:
    checkpoint_path = Path(settings.checkpoint_db_path)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(checkpoint_path, check_same_thread=False)
    checkpointer = SqliteSaver(connection)
    checkpointer.setup()
    return checkpointer, connection


def create_runtime(settings: Settings | None = None) -> RuntimeContext:
    settings = settings or load_settings()
    logger = get_logger()
    tracer = build_tracer(settings)
    checkpointer, checkpoint_connection = build_checkpointer(settings)
    patient_repository = InMemoryPatientRepository()
    appointment_repository = InMemoryAppointmentRepository()
    session_store = InMemorySessionStore()
    verification_service = VerificationService(patient_repository)
    appointment_service = AppointmentService(appointment_repository)
    session_service = SessionService(session_store, settings.session_ttl_minutes)
    provider = build_provider(settings, logger, tracer=tracer)
    graph = build_graph(
        logger=logger,
        provider=provider,
        verification_service=verification_service,
        appointment_service=appointment_service,
        max_verification_attempts=settings.max_verification_attempts,
        checkpointer=checkpointer,
    )
    workflow = LangGraphWorkflow(graph, logger, tracer=tracer)
    return RuntimeContext(
        settings=settings,
        logger=logger,
        tracer=tracer,
        checkpoint_connection=checkpoint_connection,
        graph=graph,
        workflow=workflow,
        provider=provider,
        session_service=session_service,
    )


def create_eval_runtime(settings: Settings | None = None) -> RuntimeContext:
    settings = settings or load_settings()
    logger = get_eval_logger()
    tracer = build_tracer(settings)
    checkpointer, checkpoint_connection = build_checkpointer(settings)
    patient_repository = InMemoryPatientRepository()
    appointment_repository = InMemoryAppointmentRepository()
    session_store = InMemorySessionStore()
    verification_service = VerificationService(patient_repository)
    appointment_service = AppointmentService(appointment_repository)
    session_service = SessionService(session_store, settings.session_ttl_minutes)
    provider = build_provider(settings, logger, tracer=tracer)
    graph = build_graph(
        logger=logger,
        provider=provider,
        verification_service=verification_service,
        appointment_service=appointment_service,
        max_verification_attempts=settings.max_verification_attempts,
        checkpointer=checkpointer,
    )
    workflow = LangGraphWorkflow(graph, logger, tracer=tracer)
    return RuntimeContext(
        settings=settings,
        logger=logger,
        tracer=tracer,
        checkpoint_connection=checkpoint_connection,
        graph=graph,
        workflow=workflow,
        provider=provider,
        session_service=session_service,
    )


def close_runtime(runtime: RuntimeContext | None) -> None:
    if runtime is None:
        return None
    runtime.checkpoint_connection.close()
    return None


def reset_runtime(target_app, settings: Settings | None = None) -> RuntimeContext:
    close_runtime(getattr(target_app.state, "runtime", None))
    runtime = create_runtime(settings=settings)
    target_app.state.runtime = runtime
    return runtime
