from __future__ import annotations

import pytest
import app.runtime as runtime_module

from tests.support import TestProvider


@pytest.fixture(autouse=True)
def isolate_runtime_settings(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.setenv("TRACING_ENABLED", "false")
    monkeypatch.setenv("CHECKPOINT_DB_PATH", str(tmp_path / "checkpoints.sqlite"))
    monkeypatch.setattr(runtime_module, "build_provider", lambda settings, logger, tracer=None: TestProvider())
