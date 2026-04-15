from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.config import Settings, load_settings
from app.infrastructure.llm.factory import build_provider
from app.observability import build_tracer, get_logger
from app.runtime_assembly.presenters import build_presenters
from app.runtime_assembly.repositories import build_repositories
from app.runtime_assembly.services import build_services
from app.runtime_assembly.use_cases import build_use_cases
from app.runtime_assembly.workflow import build_workflow


class RuntimeContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    settings: Settings
    logger: logging.Logger
    tracer: object | None
    graph: Any
    workflow: Any
    provider: Any
    identity_service: Any
    session_service: Any
    create_session_use_case: Any
    handle_chat_turn_use_case: Any
    forget_remembered_identity_use_case: Any


def create_runtime(settings: Settings | None = None) -> RuntimeContext:
    settings = settings or load_settings()
    logger = get_logger()
    tracer = build_tracer(settings)
    repositories = build_repositories()
    services = build_services(
        settings=settings,
        logger=logger,
        tracer=tracer,
        repositories=repositories,
        provider_factory=build_provider,
    )
    workflow_bundle = build_workflow(
        logger=logger,
        tracer=tracer,
        repositories=repositories,
        services=services,
        max_verification_attempts=settings.max_verification_attempts,
    )
    presenters = build_presenters()
    use_cases = build_use_cases(
        services=services,
        workflow_bundle=workflow_bundle,
        presenters=presenters,
    )
    return RuntimeContext(
        settings=settings,
        logger=logger,
        tracer=tracer,
        graph=workflow_bundle.graph,
        workflow=workflow_bundle.workflow,
        provider=services.provider,
        identity_service=services.identity_service,
        session_service=services.session_service,
        create_session_use_case=use_cases.create_session_use_case,
        handle_chat_turn_use_case=use_cases.handle_chat_turn_use_case,
        forget_remembered_identity_use_case=use_cases.forget_remembered_identity_use_case,
    )


def close_runtime(runtime: RuntimeContext | None) -> None:
    return None


def reset_runtime(target_app, settings: Settings | None = None) -> RuntimeContext:
    close_runtime(getattr(target_app.state, "runtime", None))
    runtime = create_runtime(settings=settings)
    target_app.state.runtime = runtime
    return runtime
