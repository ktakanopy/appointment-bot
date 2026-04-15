from __future__ import annotations

import logging
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict

from app.application.chat_service import ChatService
from app.application.session_service import SessionService
from app.config import Settings, load_settings
from app.domain.services import RememberedIdentityService
from app.graph.builder import build_graph
from app.infrastructure.persistence.in_memory import InMemoryRememberedIdentityRepository
from app.llm.base import LLMProvider
from app.llm.factory import build_provider
from app.observability import build_tracer, get_logger


class InvokableGraph(Protocol):
    def invoke(self, payload: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        ...


class RuntimeContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    settings: Settings
    logger: logging.Logger
    tracer: object | None
    graph: Any
    provider: Any
    identity_service: RememberedIdentityService
    session_service: SessionService
    chat_service: ChatService


def create_runtime(settings: Settings | None = None) -> RuntimeContext:
    settings = settings or load_settings()
    logger = get_logger()
    tracer = build_tracer(settings)
    provider = build_provider(settings, logger, tracer=tracer)
    identity_repository = InMemoryRememberedIdentityRepository()
    identity_service = RememberedIdentityService(identity_repository, settings.remembered_identity_ttl_hours)
    session_service = SessionService(settings, identity_service)
    chat_service = ChatService(identity_service, session_service)
    graph = build_graph(
        settings=settings,
        logger=logger,
        tracer=tracer,
        provider=provider,
    )
    return RuntimeContext(
        settings=settings,
        logger=logger,
        tracer=tracer,
        graph=graph,
        provider=provider,
        identity_service=identity_service,
        session_service=session_service,
        chat_service=chat_service,
    )


def close_runtime(runtime: RuntimeContext | None) -> None:
    return None
