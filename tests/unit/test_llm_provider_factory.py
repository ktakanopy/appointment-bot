from __future__ import annotations

import logging
import pytest

from app.config import load_settings
from app.infrastructure.llm.factory import build_provider


def test_build_provider_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ValueError, match="OPENAI_API_KEY is required"):
        build_provider(load_settings(), logging.getLogger("appointment_bot"))


def test_build_provider_returns_openai_provider_with_api_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    provider = build_provider(load_settings(), logging.getLogger("appointment_bot"))

    assert provider is not None
    assert provider.name == "openai"
