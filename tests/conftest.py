from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_sqlite_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("CHECKPOINT_DATABASE_PATH", str(tmp_path / "checkpoints.sqlite"))
    monkeypatch.setenv("IDENTITY_DATABASE_PATH", str(tmp_path / "remembered_identity.sqlite"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.setenv("TRACING_ENABLED", "false")
