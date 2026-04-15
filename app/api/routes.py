from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.schemas import (
    ChatRequest,
    ChatResponse,
    NewSessionResponse,
)
from app.application.errors import DependencyUnavailableError, SessionNotFoundError
from app.config import Settings
from app.runtime import RuntimeContext, create_runtime, reset_runtime as reset_runtime_context

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

    return reset_runtime_context(target_app, settings=settings)


@router.post("/sessions/new", response_model=NewSessionResponse)
async def create_session(
    runtime: RuntimeContext = Depends(get_runtime),
) -> NewSessionResponse:
    response = await asyncio.to_thread(runtime.create_session_use_case.execute)
    return NewSessionResponse(**response.model_dump(mode="json"))


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    runtime: RuntimeContext = Depends(get_runtime),
) -> ChatResponse:
    try:
        response = await asyncio.to_thread(
            runtime.handle_chat_turn_use_case.execute,
            session_id=request.session_id,
            message=request.message,
        )
    except SessionNotFoundError as error:
        raise HTTPException(status_code=404, detail="Session not found. Start a new session.") from error
    except DependencyUnavailableError as error:
        raise HTTPException(status_code=503, detail="The appointment service is temporarily unavailable.") from error
    return ChatResponse(**response.model_dump(mode="json"))
