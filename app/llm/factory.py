from __future__ import annotations

import logging

from app.config import Settings
from app.llm.base import LLMProvider
from app.llm.openai_provider import OpenAIProvider


def build_provider(
    settings: Settings,
    logger: logging.Logger,
    tracer: object | None = None,
) -> LLMProvider:
    if settings.provider.provider_name != "openai":
        raise ValueError(f"Unsupported LLM provider: {settings.provider.provider_name}")
    if not settings.provider.api_key:
        raise ValueError("OPENAI_API_KEY is required")
    return OpenAIProvider(settings.provider, logger, tracer=tracer)
