from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_new_session_defaults_to_unrestored_state():
    response = client.post("/sessions/new")

    assert response.status_code == 200
    body = response.json()
    assert body["restored_verification"] is False
    assert body["thread_id"] == body["session_id"]
    assert body["remembered_identity_status"]["status"] == "unavailable"


def test_verified_session_returns_reusable_remembered_identity():
    session = client.post("/sessions/new").json()
    session_id = session["session_id"]

    for message in ["show my appointments", "Ana Silva", "11999998888", "1990-05-10"]:
        response = client.post("/chat", json={"session_id": session_id, "message": message})

    body = response.json()
    remembered_identity_id = body["remembered_identity_status"]["remembered_identity_id"]

    assert body["verified"] is True
    assert body["remembered_identity_status"]["status"] == "active"
    assert remembered_identity_id

    restored = client.post("/sessions/new", json={"remembered_identity_id": remembered_identity_id})
    restored_body = restored.json()

    assert restored.status_code == 200
    assert restored_body["restored_verification"] is True
    assert restored_body["remembered_identity_status"]["remembered_identity_id"] == remembered_identity_id
