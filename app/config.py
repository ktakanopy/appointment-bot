from __future__ import annotations

import os

from pydantic import BaseModel, ConfigDict


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


class ProviderSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider_name: str
    model_name: str
    api_key: str | None
    timeout_seconds: int


class TracingSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    enabled: bool
    public_key: str | None
    secret_key: str | None
    host: str | None


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_ttl_minutes: int
    max_verification_attempts: int
    frontend_api_base_url: str
    provider: ProviderSettings
    tracing: TracingSettings


def load_settings() -> Settings:
    provider = ProviderSettings(
        provider_name=os.getenv("LLM_PROVIDER", "openai"),
        model_name=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        api_key=os.getenv("OPENAI_API_KEY"),
        timeout_seconds=_env_int("OPENAI_TIMEOUT_SECONDS", 20),
    )
    tracing_public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    tracing_secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    tracing_host = os.getenv("LANGFUSE_HOST")
    tracing_enabled = _env_flag("TRACING_ENABLED", bool(tracing_public_key and tracing_secret_key))
    settings = Settings(
        session_ttl_minutes=_env_int("SESSION_TTL_MINUTES", 60),
        max_verification_attempts=_env_int("MAX_VERIFICATION_ATTEMPTS", 3),
        frontend_api_base_url=os.getenv("FRONTEND_API_BASE_URL", "http://localhost:8000"),
        provider=provider,
        tracing=TracingSettings(
            enabled=tracing_enabled,
            public_key=tracing_public_key,
            secret_key=tracing_secret_key,
            host=tracing_host,
        ),
    )
    return settings
