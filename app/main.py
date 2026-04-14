from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.runtime import close_runtime, create_runtime


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.runtime = create_runtime()
    yield
    close_runtime(getattr(app.state, "runtime", None))


app = FastAPI(title="Conversational Appointment Management API", lifespan=lifespan)
app.include_router(router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content=jsonable_encoder({"detail": "Invalid chat request"}))
