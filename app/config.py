from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


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


def _env_path(name: str, default: str) -> Path:
    value = os.getenv(name, default)
    return Path(value).expanduser().resolve()


@dataclass(frozen=True, slots=True)
class ProviderSettings:
    provider_name: str
    model_name: str
    api_key: str | None
    timeout_seconds: int
    fallback_mode: str


@dataclass(frozen=True, slots=True)
class TracingSettings:
    enabled: bool
    public_key: str | None
    secret_key: str | None
    host: str | None


@dataclass(frozen=True, slots=True)
class Settings:
    checkpoint_database_path: Path
    identity_database_path: Path
    remembered_identity_ttl_hours: int
    session_ttl_minutes: int
    max_verification_attempts: int
    frontend_api_base_url: str
    provider: ProviderSettings
    tracing: TracingSettings


def load_settings() -> Settings:
    checkpoint_database_path = _env_path("CHECKPOINT_DATABASE_PATH", ".data/checkpoints.sqlite")
    identity_database_path = _env_path("IDENTITY_DATABASE_PATH", ".data/remembered_identity.sqlite")
    provider = ProviderSettings(
        provider_name=os.getenv("LLM_PROVIDER", "openai"),
        model_name=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        api_key=os.getenv("OPENAI_API_KEY"),
        timeout_seconds=_env_int("OPENAI_TIMEOUT_SECONDS", 20),
        fallback_mode=os.getenv("LLM_FALLBACK_MODE", "deterministic"),
    )
    tracing_public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    tracing_secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    tracing_host = os.getenv("LANGFUSE_HOST")
    tracing_enabled = _env_flag("TRACING_ENABLED", bool(tracing_public_key and tracing_secret_key))
    settings = Settings(
        checkpoint_database_path=checkpoint_database_path,
        identity_database_path=identity_database_path,
        remembered_identity_ttl_hours=_env_int("REMEMBERED_IDENTITY_TTL_HOURS", 24),
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
    settings.checkpoint_database_path.parent.mkdir(parents=True, exist_ok=True)
    settings.identity_database_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
