from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Any, Protocol

from app.config import Settings, load_settings
from app.domain.services import RememberedIdentityService
from app.graph.builder import build_graph
from app.llm.base import LLMProvider
from app.llm.factory import build_provider
from app.observability import build_tracer, get_logger
from app.repositories.in_memory import InMemoryRememberedIdentityRepository


class InvokableGraph(Protocol):
    def invoke(self, payload: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        ...


@dataclass(slots=True)
class SessionBootstrap:
    """Temporary bootstrap state injected into the next chat turn for a session.

    This record is created when a new session can start from previously restored
    identity information. Its state payload is merged into the first eligible
    chat request so the graph can begin with the correct verification context.
    The timestamp is used to expire stale bootstrap entries that were never
    consumed.
    """

    state: dict[str, Any]
    created_at: float


@dataclass(slots=True)
class SessionRecord:
    """Tracks a live API session registered in the in-memory runtime.

    The record keeps the public session identifier, the graph thread identifier,
    and monotonic timestamps for creation and last activity. These timestamps are
    used to validate active sessions and to evict idle sessions after the
    configured timeout.
    """

    session_id: str
    thread_id: str
    created_at: float
    last_seen_at: float


@dataclass(slots=True)
class RuntimeContext:
    """Holds the shared application runtime used by request handlers.

    A single instance is created at application startup and stored on the FastAPI
    app state. It groups immutable runtime dependencies such as settings, logger,
    tracer, graph, provider, and identity service together with mutable in-memory
    session structures. Route handlers read and update this context to resolve
    sessions, restore remembered identity, and execute the conversation graph.
    """

    settings: Settings
    logger: logging.Logger
    tracer: object | None
    graph: InvokableGraph
    provider: LLMProvider | None
    identity_service: RememberedIdentityService
    session_bootstrap: dict[str, SessionBootstrap] = field(default_factory=dict)
    sessions: dict[str, SessionRecord] = field(default_factory=dict)


def create_runtime(settings: Settings | None = None) -> RuntimeContext:
    settings = settings or load_settings()
    logger = get_logger()
    tracer = build_tracer(settings)
    provider = build_provider(settings, logger, tracer=tracer)
    identity_repository = InMemoryRememberedIdentityRepository()
    identity_service = RememberedIdentityService(identity_repository, settings.remembered_identity_ttl_hours)
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
    )


def close_runtime(runtime: RuntimeContext | None) -> None:
    return None
