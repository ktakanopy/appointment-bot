from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_api_cancel_then_reroute_back_to_list():
    session_id = client.post("/sessions/new").json()["session_id"]

    for message in ["show my appointments", "Ana Silva", "11999998888", "1990-05-10"]:
        client.post("/chat", json={"session_id": session_id, "message": message})

    canceled = client.post("/chat", json={"session_id": session_id, "message": "cancel the first one"})
    listed = client.post("/chat", json={"session_id": session_id, "message": "show me my appointments again"})

    assert canceled.status_code == 200
    assert canceled.json()["last_action_result"]["outcome"] == "canceled"
    assert canceled.json()["appointments"][0]["status"] == "canceled"
    assert "Here are your appointments:" in canceled.json()["response"]
    assert listed.status_code == 200
    assert listed.json()["appointments"][0]["status"] == "canceled"


def test_api_repeated_cancel_keeps_appointments_visible():
    session_id = client.post("/sessions/new").json()["session_id"]

    for message in ["show my appointments", "Ana Silva", "11999998888", "1990-05-10"]:
        client.post("/chat", json={"session_id": session_id, "message": message})

    client.post("/chat", json={"session_id": session_id, "message": "cancel the first one"})
    response = client.post("/chat", json={"session_id": session_id, "message": "cancel the first one"})

    assert response.status_code == 200
    body = response.json()
    assert body["last_action_result"]["outcome"] == "already_canceled"
    assert body["appointments"][0]["status"] == "canceled"
    assert "Here are your appointments:" in body["response"]
