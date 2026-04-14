from __future__ import annotations

from dataclasses import dataclass, field
import logging
import sqlite3
import time
from typing import Any, Protocol

from app.config import Settings, load_settings
from app.domain.services import RememberedIdentityService
from app.graph.builder import build_graph
from app.llm.base import LLMProvider
from app.llm.factory import build_provider
from app.observability import build_tracer, get_logger
from app.repositories.sqlite_identity import SQLiteRememberedIdentityRepository


class InvokableGraph(Protocol):
    def invoke(self, payload: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        ...

    def stream(self, payload: dict[str, Any], config: dict[str, Any]):
        ...


@dataclass(slots=True)
class SessionBootstrap:
    state: dict[str, Any]
    created_at: float


@dataclass(slots=True)
class SessionRecord:
    session_id: str
    thread_id: str
    created_at: float
    last_seen_at: float


@dataclass(slots=True)
class RuntimeContext:
    settings: Settings
    logger: logging.Logger
    tracer: object | None
    graph: InvokableGraph
    provider: LLMProvider | None
    checkpoint_connection: sqlite3.Connection
    identity_service: RememberedIdentityService
    session_bootstrap: dict[str, SessionBootstrap] = field(default_factory=dict)
    sessions: dict[str, SessionRecord] = field(default_factory=dict)


def create_runtime(settings: Settings | None = None) -> RuntimeContext:
    settings = settings or load_settings()
    logger = get_logger()
    tracer = build_tracer(settings)
    provider = build_provider(settings, logger, tracer=tracer)
    checkpoint_connection = sqlite3.connect(str(settings.checkpoint_database_path), check_same_thread=False)
    identity_repository = SQLiteRememberedIdentityRepository(settings.identity_database_path)
    identity_service = RememberedIdentityService(identity_repository, settings.remembered_identity_ttl_hours)
    graph = build_graph(
        settings=settings,
        logger=logger,
        tracer=tracer,
        provider=provider,
        checkpoint_connection=checkpoint_connection,
    )
    return RuntimeContext(
        settings=settings,
        logger=logger,
        tracer=tracer,
        graph=graph,
        provider=provider,
        checkpoint_connection=checkpoint_connection,
        identity_service=identity_service,
    )


def close_runtime(runtime: RuntimeContext | None) -> None:
    if runtime is None:
        return
    runtime.checkpoint_connection.close()
