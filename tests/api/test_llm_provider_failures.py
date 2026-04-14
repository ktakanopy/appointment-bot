from __future__ import annotations

import app.graph.builder as builder_module
import app.runtime as runtime_module
import pytest
from fastapi.testclient import TestClient

from app.api import routes
from app.main import app


client = TestClient(app)


class BrokenProvider:
    name = "broken"

    def interpret(self, message, state):
        raise RuntimeError("interpret failed")

    def generate_response(self, state, fallback_text):
        raise RuntimeError("response failed")

    def judge(self, scenario, transcript, observed_outcomes):
        raise RuntimeError("judge failed")


def test_api_raises_when_provider_fails(monkeypatch):
    monkeypatch.setattr(builder_module, "build_provider", lambda settings, logger, tracer=None: BrokenProvider())
    monkeypatch.setattr(runtime_module, "build_provider", lambda settings, logger, tracer=None: BrokenProvider())
    routes.reset_runtime(app)
    session = client.post("/sessions/new").json()

    with pytest.raises(RuntimeError, match="interpret failed"):
        client.post("/chat", json={"session_id": session["session_id"], "message": "show my appointments"})
