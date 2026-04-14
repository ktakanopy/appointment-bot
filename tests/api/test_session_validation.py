from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_chat_requires_existing_session():
    response = client.post("/chat", json={"session_id": "missing-session", "message": "hello"})

    assert response.status_code == 404
    assert response.json() == {"detail": "Session not found. Start a new session."}


def test_verification_locks_after_max_failed_attempts():
    session = client.post("/sessions/new").json()
    session_id = session["session_id"]

    for _ in range(3):
        client.post("/chat", json={"session_id": session_id, "message": "show my appointments"})
        client.post("/chat", json={"session_id": session_id, "message": "Wrong Name"})
        client.post("/chat", json={"session_id": session_id, "message": "11000000000"})
        response = client.post("/chat", json={"session_id": session_id, "message": "1999-01-01"})

    body = response.json()

    assert response.status_code == 200
    assert body["verified"] is False
    assert body["error_code"] == "verification_locked"
    assert "session is now locked" in body["response"]
