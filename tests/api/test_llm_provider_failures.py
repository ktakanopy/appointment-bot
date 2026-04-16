from __future__ import annotations

import app.runtime as runtime_module
import pytest
from fastapi.testclient import TestClient

from app.main import app, reset_runtime


client = TestClient(app)


class BrokenProvider:
    name = "broken"

    def interpret(self, message, state):
        raise RuntimeError("interpret failed")

    def judge(self, scenario, transcript, observed_outcomes):
        raise RuntimeError("judge failed")


@pytest.fixture()
def broken_provider_session(monkeypatch):
    monkeypatch.setattr(runtime_module, "build_provider", lambda settings, logger, tracer=None: BrokenProvider())
    reset_runtime(app)
    return client.post("/sessions/new").json()


def test_api_returns_503_when_provider_fails(broken_provider_session):
    response = client.post("/chat", json={"session_id": broken_provider_session["session_id"], "message": "show my appointments"})

    assert response.status_code == 503


def test_provider_failure_response_body_is_stable(broken_provider_session):
    response = client.post("/chat", json={"session_id": broken_provider_session["session_id"], "message": "show my appointments"})

    assert response.json() == {"detail": "The appointment service is temporarily unavailable."}
