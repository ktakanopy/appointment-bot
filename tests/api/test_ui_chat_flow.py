from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_ui_chat_flow_bootstraps_session_and_returns_chat_responses():
    session = client.post("/sessions/new").json()

    first = client.post(
        "/chat",
        json={"session_id": session["session_id"], "message": "show my appointments"},
    )
    second = client.post(
        "/chat",
        json={"session_id": session["session_id"], "message": "Ana Silva"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["thread_id"] == session["thread_id"]
    assert first.json()["current_operation"] == "verify_identity"
    assert "phone number" in second.json()["response"].lower()


def test_ui_chat_flow_routes_greeting_into_identity_first():
    session = client.post("/sessions/new").json()

    response = client.post(
        "/chat",
        json={"session_id": session["session_id"], "message": "hello"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["current_operation"] == "verify_identity"
    assert "full name" in body["response"].lower()
