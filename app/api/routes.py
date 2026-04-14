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
    session = SessionRecord(
        session_id=session_id,
        thread_id=thread_id,
        created_at=now,
        last_seen_at=now,
    )
    runtime.sessions[session_id] = session
    restored_verification, remembered_identity_status, response_text = _prepare_new_session_restore(
        runtime,
        request,
        session,
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
    eligible chat turn. If bootstrap state was prepared when the session was
    created, it is consumed here from the session record so it only affects the
    first relevant request. If no bootstrap state is cached but the request
    includes a remembered identity id, the function rebuilds the bootstrap state
    on demand.
    The final payload always includes the thread id and incoming message, and it
    is extended with bootstrap state when available so the graph can resume with
    the correct verification context.
    """
    _cleanup_expired_runtime_entries(runtime)
    session = _require_session(runtime, request.session_id)
    if request.remembered_identity_id:
        session.remembered_identity_id = request.remembered_identity_id
    bootstrap = session.bootstrap
    session.bootstrap = None
    if bootstrap is None and request.remembered_identity_id:
        restored_identity = runtime.identity_service.restore_identity(request.remembered_identity_id)
        bootstrap = SessionBootstrap(
            state=_build_bootstrap_state(restored_identity),
            created_at=time.monotonic(),
        )
    payload = {"thread_id": request.session_id, "incoming_message": request.message}
    if bootstrap:
        payload.update(bootstrap.state)
    return payload


def _build_chat_response(runtime: RuntimeContext, request: ChatRequest, result: dict[str, Any]) -> ChatResponse:
    session = _require_session(runtime, request.session_id)
    verification = result.get("verification", {})
    turn = result.get("turn", {})
    appointments_state = result.get("appointments", {})
    appointments = None
    if turn.get("requested_action") == "list_appointments" and appointments_state.get("listed_appointments"):
        appointments = [
            AppointmentSummary(
                id=appointment.id,
                date=appointment.date,
                time=appointment.time,
                doctor=appointment.doctor,
                status=appointment.status.value,
            )
            for appointment in appointments_state["listed_appointments"]
        ]

    last_action_result = None
    if turn.get("last_action_result"):
        last_action_result = ActionResultResponse(**turn["last_action_result"])

    remembered_identity = _ensure_remembered_identity(runtime, session, request.remembered_identity_id, result)
    remembered_identity_status = _build_identity_summary(
        runtime,
        remembered_identity,
        request.remembered_identity_id or session.remembered_identity_id,
    )

    current_action = turn.get("requested_action") or "unknown"
    if not verification.get("verified") and current_action in {"unknown", "help", "verify_identity"}:
        current_action = "verify_identity"

    return ChatResponse(
        response=turn["response_text"],
        verified=verification.get("verified", False),
        current_action=current_action,
        thread_id=request.session_id,
        appointments=appointments,
        last_action_result=last_action_result,
        error_code=turn.get("error_code"),
        remembered_identity_status=remembered_identity_status,
    )


def _ensure_remembered_identity(
    runtime: RuntimeContext,
    session: SessionRecord,
    requested_identity_id: str | None,
    result: dict[str, Any],
) -> RememberedIdentity | None:
    verification = result.get("verification", {})
    if not verification.get("verified") or not verification.get("patient_id"):
        identity_id = requested_identity_id or session.remembered_identity_id
        identity = runtime.identity_service.restore_identity(identity_id)
        if identity is not None:
            session.remembered_identity_id = identity.remembered_identity_id
        return identity
    fingerprint = runtime.identity_service.build_fingerprint(
        verification.get("provided_full_name"),
        verification.get("provided_phone"),
        verification.get("provided_dob"),
        verification["patient_id"],
    )
    identity = runtime.identity_service.ensure_identity(
        patient_id=verification["patient_id"],
        display_name=verification.get("provided_full_name"),
        verification_fingerprint=fingerprint,
    )
    session.remembered_identity_id = identity.remembered_identity_id
    return identity


def _build_bootstrap_state(
    identity: RememberedIdentity | None,
) -> ConversationState:
    if identity is None or identity.status != RememberedIdentityStatus.ACTIVE:
        return {}
    return {
        "verification": {
            "verified": True,
            "verification_status": "verified",
            "patient_id": identity.patient_id,
        }
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
    session: SessionRecord,
    now: float,
) -> tuple[bool, RememberedIdentitySummary, str]:
    """Restore remembered identity state for a newly created session when possible."""
    restored_identity = runtime.identity_service.restore_identity(request.remembered_identity_id if request else None)
    session.remembered_identity_id = (
        restored_identity.remembered_identity_id
        if restored_identity
        else request.remembered_identity_id if request else None
    )
    restored_verification = bool(restored_identity and restored_identity.status == RememberedIdentityStatus.ACTIVE)
    remembered_identity_status = _build_identity_summary(
        runtime,
        restored_identity,
        request.remembered_identity_id if request else None,
    )
    if restored_verification:
        session.bootstrap = SessionBootstrap(
            state=_build_bootstrap_state(restored_identity),
            created_at=now,
        )
        return (
            True,
            remembered_identity_status,
            f"Welcome back, {restored_identity.display_name or 'patient'}. I'm CAPY, and your identity has been restored.",
        )
    return False, remembered_identity_status, "Hello, I'm CAPY. I can help you with your appointments."


def _cleanup_expired_runtime_entries(runtime: RuntimeContext) -> None:
    """Remove expired in-memory runtime entries before handling a request.

    This clears one-time bootstrap state whose TTL has elapsed and removes
    sessions that have been idle longer than the configured session timeout.
    """
    now = time.monotonic()
    for session in runtime.sessions.values():
        if session.bootstrap and now - session.bootstrap.created_at > SESSION_BOOTSTRAP_TTL_SECONDS:
            session.bootstrap = None

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
