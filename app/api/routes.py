from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
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
from app.config import load_settings
from app.domain.models import RememberedIdentity, RememberedIdentityStatus
from app.domain.services import RememberedIdentityService, RepositoryUnavailableError
from app.graph.builder import build_graph
from app.observability import build_tracer, get_logger, record_trace_event
from app.repositories.sqlite_identity import SQLiteRememberedIdentityRepository

router = APIRouter()


@dataclass
class RuntimeContext:
    settings: Any
    logger: Any
    tracer: Any
    graph: Any
    identity_service: RememberedIdentityService
    session_bootstrap: dict[str, dict[str, Any]] = field(default_factory=dict)


def create_runtime(settings=None) -> RuntimeContext:
    settings = settings or load_settings()
    logger = get_logger()
    tracer = build_tracer(settings)
    identity_repository = SQLiteRememberedIdentityRepository(settings.identity_database_path)
    identity_service = RememberedIdentityService(identity_repository, settings.remembered_identity_ttl_hours)
    graph = build_graph(settings=settings, logger=logger)
    return RuntimeContext(
        settings=settings,
        logger=logger,
        tracer=tracer,
        graph=graph,
        identity_service=identity_service,
    )


runtime = create_runtime()
graph = runtime.graph


def reset_runtime(settings=None) -> RuntimeContext:
    global runtime, graph
    runtime = create_runtime(settings=settings)
    graph = runtime.graph
    return runtime


@router.post("/sessions/new", response_model=NewSessionResponse)
async def create_session(request: NewSessionRequest | None = None) -> NewSessionResponse:
    session_id = str(uuid4())
    thread_id = session_id
    restored_identity = runtime.identity_service.restore_identity(request.remembered_identity_id if request else None)
    restored_verification = bool(restored_identity and restored_identity.status == RememberedIdentityStatus.ACTIVE)
    remembered_identity_status = _build_identity_summary(restored_identity, request.remembered_identity_id if request else None)
    runtime.session_bootstrap[session_id] = {
        "thread_id": thread_id,
        "state": _build_bootstrap_state(restored_identity, remembered_identity_status),
    }
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
    bootstrap = runtime.session_bootstrap.get(request.session_id)
    if bootstrap is None and request.remembered_identity_id:
        restored_identity = runtime.identity_service.restore_identity(request.remembered_identity_id)
        bootstrap = {
            "thread_id": request.session_id,
            "state": _build_bootstrap_state(
                restored_identity,
                _build_identity_summary(restored_identity, request.remembered_identity_id),
            ),
        }
        runtime.session_bootstrap[request.session_id] = bootstrap
    try:
        payload = {"thread_id": request.session_id, "incoming_message": request.message}
        if bootstrap:
            payload.update(bootstrap["state"])
        record_trace_event(runtime.logger, runtime.tracer, "workflow.start", {"session_id": request.session_id, "payload": payload})
        result = graph.invoke(payload, {"configurable": {"thread_id": request.session_id}})
        record_trace_event(runtime.logger, runtime.tracer, "workflow.end", {"session_id": request.session_id, "result": result})
    except RepositoryUnavailableError as error:
        raise HTTPException(status_code=503, detail="The appointment service is temporarily unavailable.") from error
    finally:
        if request.session_id in runtime.session_bootstrap:
            del runtime.session_bootstrap[request.session_id]

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
) -> dict[str, Any]:
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
