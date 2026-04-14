from __future__ import annotations

import app.graph.builder as builder_module
import app.runtime as runtime_module
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


def test_api_returns_successful_fallback_when_provider_fails(monkeypatch):
    monkeypatch.setattr(builder_module, "build_provider", lambda settings, logger, tracer=None: BrokenProvider())
    monkeypatch.setattr(runtime_module, "build_provider", lambda settings, logger, tracer=None: BrokenProvider())
    routes.reset_runtime(app)
    session = client.post("/sessions/new").json()

    for message in ["show my appointments", "Ana Silva", "11999998888"]:
        client.post("/chat", json={"session_id": session["session_id"], "message": message})

    response = client.post("/chat", json={"session_id": session["session_id"], "message": "1990-05-10"})

    assert response.status_code == 200
    body = response.json()
    assert body["verified"] is True
    assert body["error_code"] == "provider_fallback"
