from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_api_verify_then_list_happy_path():
    session_id = client.post("/sessions/new").json()["session_id"]

    client.post("/chat", json={"session_id": session_id, "message": "I want to see my appointments"})
    client.post("/chat", json={"session_id": session_id, "message": "Ana Silva"})
    client.post("/chat", json={"session_id": session_id, "message": "11999998888"})
    response = client.post("/chat", json={"session_id": session_id, "message": "1990-05-10"})

    assert response.status_code == 200
    body = response.json()
    assert body["verified"] is True
    assert body["current_action"] == "list_appointments"
    assert len(body["appointments"]) == 2


def test_api_invalid_identity_retry_stays_generic():
    session_id = client.post("/sessions/new").json()["session_id"]

    client.post("/chat", json={"session_id": session_id, "message": "show my appointments"})
    client.post("/chat", json={"session_id": session_id, "message": "Wrong Name"})
    client.post("/chat", json={"session_id": session_id, "message": "11000000000"})
    response = client.post("/chat", json={"session_id": session_id, "message": "1999-01-01"})

    assert response.status_code == 200
    body = response.json()
    assert body["verified"] is False
    assert "couldn't verify your identity" in body["response"]
    assert body.get("appointments") is None


def test_api_identify_request_starts_verification_before_capabilities():
    session_id = client.post("/sessions/new").json()["session_id"]

    response = client.post("/chat", json={"session_id": session_id, "message": "identify"})

    assert response.status_code == 200
    body = response.json()
    assert body["verified"] is False
    assert body["current_action"] == "verify_identity"
    assert "full name" in body["response"].lower()
