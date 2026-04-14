from __future__ import annotations

import asyncio
import time
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request

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
from app.config import Settings
from app.domain.models import RememberedIdentity, RememberedIdentityStatus
from app.domain.services import RepositoryUnavailableError
from app.graph.state import ConversationState
from app.observability import record_trace_event
from app.runtime import RuntimeContext, SessionBootstrap, SessionRecord, close_runtime, create_runtime

router = APIRouter()
SESSION_BOOTSTRAP_TTL_SECONDS = 300


def get_runtime(request: Request) -> RuntimeContext:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None:
        runtime = create_runtime()
        request.app.state.runtime = runtime
    return runtime


def reset_runtime(target_app=None, settings: Settings | None = None) -> RuntimeContext:
    if target_app is None:
        from app.main import app as target_app

    close_runtime(getattr(target_app.state, "runtime", None))
    runtime = create_runtime(settings=settings)
    target_app.state.runtime = runtime
    return runtime


@router.post("/sessions/new", response_model=NewSessionResponse)
async def create_session(
    request: NewSessionRequest | None = None,
    runtime: RuntimeContext = Depends(get_runtime),
) -> NewSessionResponse:
    """Create a new session and pre-load restored identity state when available."""
    _cleanup_expired_runtime_entries(runtime)
    session_id = str(uuid4())
    thread_id = session_id
    now = time.monotonic()
    runtime.sessions[session_id] = SessionRecord(
        session_id=session_id,
        thread_id=thread_id,
        created_at=now,
        last_seen_at=now,
    )
    restored_verification, remembered_identity_status, response_text = _prepare_new_session_restore(
        runtime,
        request,
        session_id,
        now,
    )
    return NewSessionResponse(
        session_id=session_id,
        thread_id=thread_id,
        restored_verification=restored_verification,
        remembered_identity_status=remembered_identity_status,
        response=response_text,
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    runtime: RuntimeContext = Depends(get_runtime),
) -> ChatResponse:
    """Process a chat turn for an existing session and return the graph result.

    The handler validates session-scoped runtime state, builds the graph input
    payload from the incoming message and any restored identity context, and
    executes the synchronous LangGraph workflow in a worker thread so the async
    request handler does not block the event loop. Repository availability
    failures are translated into HTTP 503 responses, and successful graph output
    is converted into the public chat response model returned by the API.
    """
    payload = _build_chat_payload(runtime, request)
    config = {"configurable": {"thread_id": request.session_id}}
    record_trace_event(runtime.logger, runtime.tracer, "workflow.start", {"session_id": request.session_id, "payload": payload})
    try:
        result = await asyncio.to_thread(runtime.graph.invoke, payload, config)
    except RepositoryUnavailableError as error:
        raise HTTPException(status_code=503, detail="The appointment service is temporarily unavailable.") from error
    record_trace_event(runtime.logger, runtime.tracer, "workflow.end", {"session_id": request.session_id, "result": result})
    return _build_chat_response(runtime, request, result)


@router.post("/remembered-identity/forget", response_model=ForgetRememberedIdentityResponse)
async def forget_remembered_identity(
    request: ForgetRememberedIdentityRequest,
    runtime: RuntimeContext = Depends(get_runtime),
) -> ForgetRememberedIdentityResponse:
    cleared = runtime.identity_service.revoke_identity(request.remembered_identity_id)
    return ForgetRememberedIdentityResponse(cleared=cleared)


def _build_chat_payload(runtime: RuntimeContext, request: ChatRequest) -> dict[str, Any]:
    """Build the graph input payload for a chat turn within an existing session.

    The function starts by removing expired runtime entries so stale session
    records and one-time bootstrap state do not leak into a new request. It then
    calls `_require_session()` to ensure the provided session id was created by
    `/sessions/new`, refresh the session activity timestamp, and fail fast with a
    404 if the session is unknown or has already been cleaned up.

    Bootstrap state is used to inject restored identity context into the next
    eligible chat turn. If a bootstrap entry was prepared when the session was
    created, it is consumed here with `pop()` so it only affects the first
    relevant request. If no bootstrap entry is cached but the request includes a
    remembered identity id, the function rebuilds the bootstrap state on demand.
    The final payload always includes the thread id and incoming message, and it
    is extended with bootstrap state when available so the graph can resume with
    the correct verification context.
    """
    _cleanup_expired_runtime_entries(runtime)
    _require_session(runtime, request.session_id)
    bootstrap = runtime.session_bootstrap.pop(request.session_id, None)
    if bootstrap is None and request.remembered_identity_id:
        restored_identity = runtime.identity_service.restore_identity(request.remembered_identity_id)
        bootstrap = SessionBootstrap(
            state=_build_bootstrap_state(
                restored_identity,
                _build_identity_summary(runtime, restored_identity, request.remembered_identity_id),
            ),
            created_at=time.monotonic(),
        )
    payload = {"thread_id": request.session_id, "incoming_message": request.message}
    if bootstrap:
        payload.update(bootstrap.state)
    return payload


def _build_chat_response(runtime: RuntimeContext, request: ChatRequest, result: dict[str, Any]) -> ChatResponse:
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

    remembered_identity = _ensure_remembered_identity(runtime, result)
    remembered_identity_status = _build_identity_summary(
        runtime,
        remembered_identity,
        request.remembered_identity_id,
    )

    current_action = result.get("requested_action") or "unknown"
    if not result.get("verified") and current_action in {"unknown", "help", "verify_identity"}:
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


def _ensure_remembered_identity(runtime: RuntimeContext, result: dict[str, Any]) -> RememberedIdentity | None:
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
    runtime: RuntimeContext,
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


def _prepare_new_session_restore(
    runtime: RuntimeContext,
    request: NewSessionRequest | None,
    session_id: str,
    now: float,
) -> tuple[bool, RememberedIdentitySummary, str]:
    """Restore remembered identity state for a newly created session when possible."""
    restored_identity = runtime.identity_service.restore_identity(request.remembered_identity_id if request else None)
    restored_verification = bool(restored_identity and restored_identity.status == RememberedIdentityStatus.ACTIVE)
    remembered_identity_status = _build_identity_summary(
        runtime,
        restored_identity,
        request.remembered_identity_id if request else None,
    )
    if restored_verification:
        runtime.session_bootstrap[session_id] = SessionBootstrap(
            state=_build_bootstrap_state(restored_identity, remembered_identity_status),
            created_at=now,
        )
        return (
            True,
            remembered_identity_status,
            f"Welcome back, {restored_identity.display_name or 'patient'}. Your identity has been restored.",
        )
    return False, remembered_identity_status, "New session started."


def _cleanup_expired_runtime_entries(runtime: RuntimeContext) -> None:
    """Remove expired in-memory runtime entries before handling a request.

    This drops one-time bootstrap state whose TTL has elapsed and removes
    sessions that have been idle longer than the configured session timeout.
    """
    now = time.monotonic()
    expired_bootstrap_session_ids = [
        session_id
        for session_id, bootstrap in runtime.session_bootstrap.items()
        if now - bootstrap.created_at > SESSION_BOOTSTRAP_TTL_SECONDS
    ]
    for session_id in expired_bootstrap_session_ids:
        del runtime.session_bootstrap[session_id]

    session_ttl_seconds = runtime.settings.session_ttl_minutes * 60
    expired_session_ids = [
        session_id
        for session_id, session in runtime.sessions.items()
        if now - session.last_seen_at > session_ttl_seconds
    ]
    for session_id in expired_session_ids:
        del runtime.sessions[session_id]


def _require_session(runtime: RuntimeContext, session_id: str) -> SessionRecord:
    session = runtime.sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found. Start a new session.")
    session.last_seen_at = time.monotonic()
    return session
