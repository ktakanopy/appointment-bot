from __future__ import annotations

from dataclasses import dataclass, field
import logging
import sqlite3
import time
from typing import Any, Protocol
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app.api.schemas import (
    ActionResultResponse,
    AppointmentSummary,
    ChatRequest,
    ChatResponse,
    ForgetRememberedIdentityRequest,
    ForgetRememberedIdentityResponse,
    NewSessionRequest,
    NewSessionResponse,
    RememberedIdentitySummary,
)
from app.config import Settings, load_settings
from app.domain.models import RememberedIdentity, RememberedIdentityStatus
from app.domain.services import RememberedIdentityService, RepositoryUnavailableError
from app.graph.builder import build_graph
from app.graph.state import ConversationState
from app.llm.base import LLMProvider
from app.llm.factory import build_provider
from app.observability import build_tracer, get_logger, record_trace_event
from app.repositories.sqlite_identity import SQLiteRememberedIdentityRepository

router = APIRouter()
SESSION_BOOTSTRAP_TTL_SECONDS = 300


class InvokableGraph(Protocol):
    def invoke(self, payload: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        ...


@dataclass(slots=True)
class SessionBootstrap:
    state: ConversationState
    created_at: float


@dataclass
class RuntimeContext:
    settings: Settings
    logger: logging.Logger
    tracer: object | None
    graph: InvokableGraph
    provider: LLMProvider | None
    checkpoint_connection: sqlite3.Connection
    identity_service: RememberedIdentityService
    session_bootstrap: dict[str, SessionBootstrap] = field(default_factory=dict)


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


runtime = create_runtime()
graph = runtime.graph


def reset_runtime(settings: Settings | None = None) -> RuntimeContext:
    global runtime, graph
    runtime.checkpoint_connection.close()
    runtime = create_runtime(settings=settings)
    graph = runtime.graph
    return runtime


@router.post("/sessions/new", response_model=NewSessionResponse)
async def create_session(request: NewSessionRequest | None = None) -> NewSessionResponse:
    _cleanup_expired_bootstrap_entries()
    session_id = str(uuid4())
    thread_id = session_id
    restored_identity = runtime.identity_service.restore_identity(request.remembered_identity_id if request else None)
    restored_verification = bool(restored_identity and restored_identity.status == RememberedIdentityStatus.ACTIVE)
    remembered_identity_status = _build_identity_summary(restored_identity, request.remembered_identity_id if request else None)
    if restored_verification:
        runtime.session_bootstrap[session_id] = SessionBootstrap(
            state=_build_bootstrap_state(restored_identity, remembered_identity_status),
            created_at=time.monotonic(),
        )
    if restored_verification:
        response_text = f"Welcome back, {restored_identity.display_name or 'patient'}. Your identity has been restored."
    else:
        response_text = "New session started."
    return NewSessionResponse(
        session_id=session_id,
        thread_id=thread_id,
        restored_verification=restored_verification,
        remembered_identity_status=remembered_identity_status,
        response=response_text,
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    _cleanup_expired_bootstrap_entries()
    bootstrap = runtime.session_bootstrap.pop(request.session_id, None)
    if bootstrap is None and request.remembered_identity_id:
        restored_identity = runtime.identity_service.restore_identity(request.remembered_identity_id)
        bootstrap = SessionBootstrap(
            state=_build_bootstrap_state(
                restored_identity,
                _build_identity_summary(restored_identity, request.remembered_identity_id),
            ),
            created_at=time.monotonic(),
        )
    try:
        payload = {"thread_id": request.session_id, "incoming_message": request.message}
        if bootstrap:
            payload.update(bootstrap.state)
        record_trace_event(runtime.logger, runtime.tracer, "workflow.start", {"session_id": request.session_id, "payload": payload})
        result = graph.invoke(payload, {"configurable": {"thread_id": request.session_id}})
        record_trace_event(runtime.logger, runtime.tracer, "workflow.end", {"session_id": request.session_id, "result": result})
    except RepositoryUnavailableError as error:
        raise HTTPException(status_code=503, detail="The appointment service is temporarily unavailable.") from error

    appointments = None
    if result.get("requested_action") == "list_appointments" and result.get("listed_appointments"):
        appointments = [
            AppointmentSummary(
                id=appointment.id,
                date=appointment.date,
                time=appointment.time,
                doctor=appointment.doctor,
                status=appointment.status.value,
            )
            for appointment in result["listed_appointments"]
        ]

    last_action_result = None
    if result.get("last_action_result"):
        last_action_result = ActionResultResponse(**result["last_action_result"])

    remembered_identity = _ensure_remembered_identity(result)
    remembered_identity_status = _build_identity_summary(
        remembered_identity,
        request.remembered_identity_id,
    )

    current_action = result.get("requested_action") or "unknown"
    if not result.get("verified") and current_action == "unknown":
        current_action = "verify_identity"

    return ChatResponse(
        response=result["response_text"],
        verified=result.get("verified", False),
        current_action=current_action,
        thread_id=request.session_id,
        appointments=appointments,
        last_action_result=last_action_result,
        error_code=result.get("error_code"),
        remembered_identity_status=remembered_identity_status,
    )


@router.post("/remembered-identity/forget", response_model=ForgetRememberedIdentityResponse)
async def forget_remembered_identity(
    request: ForgetRememberedIdentityRequest,
) -> ForgetRememberedIdentityResponse:
    cleared = runtime.identity_service.revoke_identity(request.remembered_identity_id)
    return ForgetRememberedIdentityResponse(cleared=cleared)


def _ensure_remembered_identity(result: dict[str, Any]) -> RememberedIdentity | None:
    if not result.get("verified") or not result.get("patient_id"):
        remembered_identity_id = result.get("remembered_identity_id")
        return runtime.identity_service.restore_identity(remembered_identity_id)
    fingerprint = runtime.identity_service.build_fingerprint(
        result.get("provided_full_name"),
        result.get("provided_phone"),
        result.get("provided_dob"),
        result["patient_id"],
    )
    identity = runtime.identity_service.ensure_identity(
        patient_id=result["patient_id"],
        display_name=result.get("provided_full_name"),
        verification_fingerprint=fingerprint,
    )
    result["remembered_identity_id"] = identity.remembered_identity_id
    result["remembered_identity_status"] = runtime.identity_service.summary_for_identity(identity)
    return identity


def _build_bootstrap_state(
    identity: RememberedIdentity | None,
    remembered_identity_status: RememberedIdentitySummary,
) -> ConversationState:
    if identity is None or identity.status != RememberedIdentityStatus.ACTIVE:
        return {"remembered_identity_status": remembered_identity_status.model_dump()}
    return {
        "verified": True,
        "verification_status": "verified",
        "patient_id": identity.patient_id,
        "remembered_identity_id": identity.remembered_identity_id,
        "remembered_identity_status": remembered_identity_status.model_dump(),
    }


def _build_identity_summary(
    identity: RememberedIdentity | None,
    requested_identity_id: str | None = None,
) -> RememberedIdentitySummary:
    if identity is None:
        return RememberedIdentitySummary(
            remembered_identity_id=requested_identity_id or "",
            status=RememberedIdentityStatus.UNAVAILABLE.value,
            display_name=None,
            expires_at=None,
        )
    return RememberedIdentitySummary(**runtime.identity_service.summary_for_identity(identity))


def _cleanup_expired_bootstrap_entries() -> None:
    now = time.monotonic()
    expired_session_ids = [
        session_id
        for session_id, bootstrap in runtime.session_bootstrap.items()
        if now - bootstrap.created_at > SESSION_BOOTSTRAP_TTL_SECONDS
    ]
    for session_id in expired_session_ids:
        del runtime.session_bootstrap[session_id]
