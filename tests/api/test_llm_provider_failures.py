from __future__ import annotations

import app.runtime as runtime_module
from fastapi.testclient import TestClient

from app.main import app, reset_runtime


client = TestClient(app)


class BrokenProvider:
    name = "broken"

    def interpret(self, message, state):
        raise RuntimeError("interpret failed")

    def judge(self, scenario, transcript, observed_outcomes):
        raise RuntimeError("judge failed")


def test_api_returns_503_when_provider_fails(monkeypatch):
    monkeypatch.setattr(runtime_module, "build_provider", lambda settings, logger, tracer=None: BrokenProvider())
    reset_runtime(app)
    session = client.post("/sessions/new").json()

    response = client.post("/chat", json={"session_id": session["session_id"], "message": "show my appointments"})

    assert response.status_code == 503


def test_provider_failure_response_body_is_stable(monkeypatch):
    monkeypatch.setattr(runtime_module, "build_provider", lambda settings, logger, tracer=None: BrokenProvider())
    reset_runtime(app)
    session = client.post("/sessions/new").json()

    response = client.post("/chat", json={"session_id": session["session_id"], "message": "show my appointments"})

    assert response.json() == {"detail": "The appointment service is temporarily unavailable."}
