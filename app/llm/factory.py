from __future__ import annotations

from app.llm.openai_provider import OpenAIProvider
from app.observability import build_tracer


def build_provider(settings, logger):
    if settings.provider.provider_name != "openai":
        return None
    if not settings.provider.api_key:
        return None
    tracer = build_tracer(settings)
    return OpenAIProvider(settings.provider, logger, tracer=tracer)
