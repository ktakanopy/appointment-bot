from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.schemas import (
    ChatRequest,
    ChatResponse,
    ForgetRememberedIdentityRequest,
    ForgetRememberedIdentityResponse,
    NewSessionRequest,
    NewSessionResponse,
)
from app.application.session_service import SessionNotFoundError
from app.config import Settings
from app.domain.errors import RepositoryUnavailableError
from app.observability import record_trace_event
from app.runtime import RuntimeContext, close_runtime, create_runtime

router = APIRouter()


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
    response = runtime.session_service.create_session(
        request.remembered_identity_id if request is not None else None
    )
    return NewSessionResponse(**response)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    runtime: RuntimeContext = Depends(get_runtime),
) -> ChatResponse:
    try:
        payload = runtime.chat_service.build_payload(
            request.session_id,
            request.message,
            request.remembered_identity_id,
        )
    except SessionNotFoundError as error:
        raise HTTPException(status_code=404, detail="Session not found. Start a new session.") from error
    config = {"configurable": {"thread_id": request.session_id}}
    record_trace_event(runtime.logger, runtime.tracer, "workflow.start", {"session_id": request.session_id, "payload": payload})
    try:
        result = await asyncio.to_thread(runtime.graph.invoke, payload, config)
    except RepositoryUnavailableError as error:
        raise HTTPException(status_code=503, detail="The appointment service is temporarily unavailable.") from error
    record_trace_event(runtime.logger, runtime.tracer, "workflow.end", {"session_id": request.session_id, "result": result})
    try:
        response = runtime.chat_service.build_response(
            request.session_id,
            request.remembered_identity_id,
            result,
        )
    except SessionNotFoundError as error:
        raise HTTPException(status_code=404, detail="Session not found. Start a new session.") from error
    return ChatResponse(**response)


@router.post("/remembered-identity/forget", response_model=ForgetRememberedIdentityResponse)
async def forget_remembered_identity(
    request: ForgetRememberedIdentityRequest,
    runtime: RuntimeContext = Depends(get_runtime),
) -> ForgetRememberedIdentityResponse:
    cleared = runtime.identity_service.revoke_identity(request.remembered_identity_id)
    return ForgetRememberedIdentityResponse(cleared=cleared)
