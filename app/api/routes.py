from __future__ import annotations

import asyncio
import json
import threading
import time
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

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
async def chat(
    request: ChatRequest,
    runtime: RuntimeContext = Depends(get_runtime),
) -> ChatResponse:
    payload = _build_chat_payload(runtime, request)
    config = {"configurable": {"thread_id": request.session_id}}
    record_trace_event(runtime.logger, runtime.tracer, "workflow.start", {"session_id": request.session_id, "payload": payload})
    try:
        result = await asyncio.to_thread(runtime.graph.invoke, payload, config)
    except RepositoryUnavailableError as error:
        raise HTTPException(status_code=503, detail="The appointment service is temporarily unavailable.") from error
    record_trace_event(runtime.logger, runtime.tracer, "workflow.end", {"session_id": request.session_id, "result": result})
    return _build_chat_response(runtime, request, result)


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    runtime: RuntimeContext = Depends(get_runtime),
) -> StreamingResponse:
    payload = _build_chat_payload(runtime, request)
    config = {"configurable": {"thread_id": request.session_id}}
    queue: asyncio.Queue[tuple[str, dict[str, Any] | None]] = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def publish(event_name: str, data: dict[str, Any] | None) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, (event_name, data))

    def produce() -> None:
        final_result: dict[str, Any] | None = None
        try:
            record_trace_event(runtime.logger, runtime.tracer, "workflow.start", {"session_id": request.session_id, "payload": payload})
            for chunk in runtime.graph.stream(payload, config):
                if not chunk:
                    continue
                node_name, node_state = next(iter(chunk.items()))
                final_result = node_state
                publish("node", _build_stream_node_event(node_name, node_state))
            if final_result is None:
                publish("error", {"detail": "The chat stream did not produce a result.", "error_code": "empty_stream"})
                return
            record_trace_event(runtime.logger, runtime.tracer, "workflow.end", {"session_id": request.session_id, "result": final_result})
            publish("message", _build_chat_response(runtime, request, final_result).model_dump())
            publish("done", {"thread_id": request.session_id})
        except RepositoryUnavailableError:
            publish("error", {"detail": "The appointment service is temporarily unavailable.", "error_code": "service_unavailable"})
        except Exception:
            publish("error", {"detail": "The chat stream failed.", "error_code": "stream_failed"})
        finally:
            publish("__end__", None)

    threading.Thread(target=produce, daemon=True).start()

    async def event_stream():
        while True:
            event_name, data = await queue.get()
            if event_name == "__end__":
                break
            yield _format_sse(event_name, data or {})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/remembered-identity/forget", response_model=ForgetRememberedIdentityResponse)
async def forget_remembered_identity(
    request: ForgetRememberedIdentityRequest,
    runtime: RuntimeContext = Depends(get_runtime),
) -> ForgetRememberedIdentityResponse:
    cleared = runtime.identity_service.revoke_identity(request.remembered_identity_id)
    return ForgetRememberedIdentityResponse(cleared=cleared)


def _build_chat_payload(runtime: RuntimeContext, request: ChatRequest) -> dict[str, Any]:
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


def _build_stream_node_event(node_name: str, state: dict[str, Any]) -> dict[str, Any]:
    current_action = state.get("requested_action") or "unknown"
    if not state.get("verified") and current_action in {"unknown", "help", "verify_identity"}:
        current_action = "verify_identity"
    return {
        "node": node_name,
        "current_action": current_action,
        "verified": state.get("verified", False),
        "verification_status": state.get("verification_status"),
        "error_code": state.get("error_code"),
    }


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


def _cleanup_expired_runtime_entries(runtime: RuntimeContext) -> None:
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


def _format_sse(event_name: str, data: dict[str, Any]) -> str:
    return f"event: {event_name}\ndata: {json.dumps(data, ensure_ascii=True)}\n\n"
