from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.models import (
    ChatRequest,
    ChatTurnResponse,
    DependencyUnavailableError,
    HealthResponse,
    NewSessionResponseData,
    SessionNotFoundError,
)
from app.responses import build_chat_response, build_new_session_response, build_response_text
from app.runtime import RuntimeContext, close_runtime, create_runtime, reset_runtime as reset_runtime_context


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the FastAPI application lifecycle.

    This function is an async context manager used by FastAPI to run startup
    and shutdown logic around the application. It creates the shared runtime
    before the app starts serving requests and closes it when the app stops,
    which is useful because it centralizes dependency setup and cleanup in one
    place instead of rebuilding runtime state on every request.
    """
    app.state.runtime = create_runtime()
    yield
    close_runtime(getattr(app.state, "runtime", None))


app = FastAPI(title="Conversational Appointment Management API", lifespan=lifespan)


def get_runtime(request: Request) -> RuntimeContext:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None:
        runtime = create_runtime()
        request.app.state.runtime = runtime
    return runtime


def reset_runtime(target_app=None, settings=None) -> RuntimeContext:
    """Rebuild the shared application runtime.

    This function replaces the current runtime stored on the FastAPI app with a
    freshly created one, optionally using custom settings. It is useful for
    tests and runtime reconfiguration because it gives the application a clean
    set of dependencies without restarting the whole process.
    """
    if target_app is None:
        target_app = app
    return reset_runtime_context(target_app, settings=settings)


@app.post("/sessions/new", response_model=NewSessionResponseData)
def create_session(
    runtime: RuntimeContext = Depends(get_runtime),
) -> NewSessionResponseData:
    runtime.session_service.cleanup_expired()
    session = runtime.session_service.create_session()
    response = build_new_session_response(session)
    if response.response is not None:
        runtime.workflow.append_assistant_message(session.thread_id, response.response)
    return response


@app.post("/chat", response_model=ChatTurnResponse)
def chat(
    request: ChatRequest,
    runtime: RuntimeContext = Depends(get_runtime),
) -> ChatTurnResponse:
    try:
        runtime.session_service.cleanup_expired()
        session = runtime.session_service.require_session(request.session_id)
        state = runtime.workflow.run(session.thread_id, request.message)
        response_text = build_response_text(state)
        runtime.workflow.append_assistant_message(session.thread_id, response_text)
        return build_chat_response(session.thread_id, response_text, state)
    except SessionNotFoundError as error:
        raise HTTPException(status_code=404, detail="Session not found. Start a new session.") from error
    except DependencyUnavailableError as error:
        raise HTTPException(status_code=503, detail="The appointment service is temporarily unavailable.") from error


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    _ = request
    _ = exc
    return JSONResponse(status_code=422, content=jsonable_encoder({"detail": "Invalid chat request"}))
