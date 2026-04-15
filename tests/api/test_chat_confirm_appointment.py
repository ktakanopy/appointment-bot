from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_api_confirm_first_appointment():
    session_id = client.post("/sessions/new").json()["session_id"]

    for message in ["show my appointments", "Ana Silva", "11999998888", "1990-05-10"]:
        client.post("/chat", json={"session_id": session_id, "message": message})

    response = client.post("/chat", json={"session_id": session_id, "message": "confirm the first one"})

    assert response.status_code == 200
    body = response.json()
    assert body["current_operation"] == "confirm_appointment"
    assert body["last_action_result"]["outcome"] == "confirmed"
    assert len(body["appointments"]) == 2
    assert body["appointments"][0]["status"] == "confirmed"
    assert "Confirmed. Here is your updated appointment list." in body["response"]


def test_api_confirm_numeric_reference_uses_patient_facing_numbering():
    session_id = client.post("/sessions/new").json()["session_id"]

    for message in ["show my appointments", "Ana Silva", "11999998888", "1990-05-10"]:
        client.post("/chat", json={"session_id": session_id, "message": message})

    response = client.post("/chat", json={"session_id": session_id, "message": "confirm appointment 1"})

    assert response.status_code == 200
    body = response.json()
    assert body["current_operation"] == "confirm_appointment"
    assert body["last_action_result"]["appointment_id"] == "a1"
    assert body["last_action_result"]["outcome"] == "confirmed"


def test_api_confirm_after_verification_only_flow_uses_auto_list_context():
    session_id = client.post("/sessions/new").json()["session_id"]

    for message in ["Ana Silva", "11999998888", "1990-05-10"]:
        client.post("/chat", json={"session_id": session_id, "message": message})

    response = client.post("/chat", json={"session_id": session_id, "message": "confirm the first one"})

    assert response.status_code == 200
    body = response.json()
    assert body["current_operation"] == "confirm_appointment"
    assert body["last_action_result"]["appointment_id"] == "a1"
    assert body["last_action_result"]["outcome"] == "confirmed"


def test_api_repeated_confirm_keeps_appointments_visible():
    session_id = client.post("/sessions/new").json()["session_id"]

    for message in ["show my appointments", "Ana Silva", "11999998888", "1990-05-10"]:
        client.post("/chat", json={"session_id": session_id, "message": message})

    client.post("/chat", json={"session_id": session_id, "message": "confirm the first one"})
    response = client.post("/chat", json={"session_id": session_id, "message": "confirm the first one"})

    assert response.status_code == 200
    body = response.json()
    assert body["last_action_result"]["outcome"] == "already_confirmed"
    assert body["appointments"][0]["status"] == "confirmed"
    assert "That appointment was already confirmed. Here is your updated appointment list." in body["response"]
