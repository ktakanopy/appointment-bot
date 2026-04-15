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
    assert body["current_operation"] == "list_appointments"
    assert len(body["appointments"]) == 2
    assert "Would you like to confirm or cancel any of them?" in body["response"]


def test_api_invalid_identity_explains_mismatch():
    session_id = client.post("/sessions/new").json()["session_id"]

    client.post("/chat", json={"session_id": session_id, "message": "show my appointments"})
    client.post("/chat", json={"session_id": session_id, "message": "Wrong Name"})
    client.post("/chat", json={"session_id": session_id, "message": "11000000000"})
    response = client.post("/chat", json={"session_id": session_id, "message": "1999-01-01"})

    assert response.status_code == 200
    body = response.json()
    assert body["verified"] is False
    assert "do not match our records" in body["response"]
    assert body["issue"] == "invalid_identity"
    assert body.get("appointments") is None


def test_api_invalid_dob_format_explains_why_and_allows_retry():
    session_id = client.post("/sessions/new").json()["session_id"]

    client.post("/chat", json={"session_id": session_id, "message": "show my appointments"})
    client.post("/chat", json={"session_id": session_id, "message": "Ana Silva"})
    client.post("/chat", json={"session_id": session_id, "message": "11999998888"})
    invalid_response = client.post("/chat", json={"session_id": session_id, "message": "1994-28-09"})

    assert invalid_response.status_code == 200
    invalid_body = invalid_response.json()
    assert invalid_body["verified"] is False
    assert invalid_body["issue"] == "invalid_dob"
    assert "date of birth looks invalid" in invalid_body["response"]

    valid_response = client.post("/chat", json={"session_id": session_id, "message": "1990-05-10"})

    assert valid_response.status_code == 200
    valid_body = valid_response.json()
    assert valid_body["verified"] is True
    assert valid_body["current_operation"] == "list_appointments"
    assert len(valid_body["appointments"]) == 2
    assert "Would you like to confirm or cancel any of them?" in valid_body["response"]


def test_api_identify_request_starts_verification_before_capabilities():
    session_id = client.post("/sessions/new").json()["session_id"]

    response = client.post("/chat", json={"session_id": session_id, "message": "identify"})

    assert response.status_code == 200
    body = response.json()
    assert body["verified"] is False
    assert body["current_operation"] == "verify_identity"
    assert "full name" in body["response"].lower()


def test_api_verification_without_deferred_action_auto_lists_appointments():
    session_id = client.post("/sessions/new").json()["session_id"]

    client.post("/chat", json={"session_id": session_id, "message": "Ana Silva"})
    client.post("/chat", json={"session_id": session_id, "message": "11999998888"})
    response = client.post("/chat", json={"session_id": session_id, "message": "1990-05-10"})

    assert response.status_code == 200
    body = response.json()
    assert body["verified"] is True
    assert body["current_operation"] == "list_appointments"
    assert len(body["appointments"]) == 2
    assert "Would you like to confirm or cancel any of them?" in body["response"]
