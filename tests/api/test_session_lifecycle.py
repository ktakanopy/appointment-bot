from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_new_session_returns_core_session_payload():
    response = client.post("/sessions/new")

    assert response.status_code == 200
    body = response.json()
    assert body["thread_id"] == body["session_id"]
    assert "remembered_identity_status" not in body
    assert body["response"] == "Hello, I'm CAPY. I can help you with your appointments."


def test_new_session_starts_unverified_even_after_a_previous_verified_session():
    first_session_id = client.post("/sessions/new").json()["session_id"]

    for message in ["show my appointments", "Ana Silva", "11999998888", "1990-05-10"]:
        response = client.post("/chat", json={"session_id": first_session_id, "message": message})

    body = response.json()
    assert body["verified"] is True

    second_session = client.post("/sessions/new").json()
    follow_up = client.post(
        "/chat",
        json={"session_id": second_session["session_id"], "message": "show my appointments"},
    )
    follow_up_body = follow_up.json()

    assert follow_up.status_code == 200
    assert follow_up_body["verified"] is False
    assert follow_up_body["current_operation"] == "verify_identity"
