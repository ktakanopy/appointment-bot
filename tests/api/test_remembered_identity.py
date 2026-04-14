from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_forget_remembered_identity_revokes_future_restore():
    session = client.post("/sessions/new").json()
    for message in ["show my appointments", "Ana Silva", "11999998888", "1990-05-10"]:
        response = client.post("/chat", json={"session_id": session["session_id"], "message": message})

    remembered_identity_id = response.json()["remembered_identity_status"]["remembered_identity_id"]
    forget = client.post("/remembered-identity/forget", json={"remembered_identity_id": remembered_identity_id})
    restored = client.post("/sessions/new", json={"remembered_identity_id": remembered_identity_id})

    assert forget.status_code == 200
    assert forget.json()["cleared"] is True
    assert restored.json()["restored_verification"] is False
    assert restored.json()["remembered_identity_status"]["status"] == "revoked"
