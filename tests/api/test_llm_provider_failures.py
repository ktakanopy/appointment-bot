from __future__ import annotations

import app.runtime as runtime_module
import app.graph.nodes as graph_nodes
from fastapi.testclient import TestClient

from app.main import app, reset_runtime


client = TestClient(app)


class BrokenProvider:
    name = "broken"

    def interpret(self, message, state):
        raise RuntimeError("interpret failed")

    def judge(self, scenario, transcript, observed_outcomes):
        raise RuntimeError("judge failed")


def test_api_uses_fallback_when_provider_fails(monkeypatch):
    monkeypatch.setattr(runtime_module, "build_provider", lambda settings, logger, tracer=None: BrokenProvider())
    reset_runtime(app)
    session = client.post("/sessions/new").json()

    response = client.post("/chat", json={"session_id": session["session_id"], "message": "show my appointments"})

    assert response.status_code == 200
    body = response.json()
    assert body["verified"] is False
    assert body["current_operation"] == "list_appointments"
    assert body["response_key"] == "collect_full_name"


def test_api_returns_503_when_provider_and_fallback_fail(monkeypatch):
    monkeypatch.setattr(runtime_module, "build_provider", lambda settings, logger, tracer=None: BrokenProvider())

    def fail_requested_operation(message, state):
        raise RuntimeError("fallback failed")

    monkeypatch.setattr(graph_nodes, "extract_requested_operation", fail_requested_operation)
    reset_runtime(app)
    session = client.post("/sessions/new").json()

    response = client.post("/chat", json={"session_id": session["session_id"], "message": "show my appointments"})

    assert response.status_code == 503
    assert response.json()["detail"] == "The appointment service is temporarily unavailable."
