from __future__ import annotations

import logging

from app.config import Settings
from app.llm.base import LLMProvider
from app.llm.openai_provider import OpenAIProvider


def build_provider(
    settings: Settings,
    logger: logging.Logger,
    tracer: object | None = None,
) -> LLMProvider | None:
    if settings.provider.provider_name != "openai":
        return None
    if not settings.provider.api_key:
        return None
    return OpenAIProvider(settings.provider, logger, tracer=tracer)
