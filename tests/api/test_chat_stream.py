import json

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_chat_stream_emits_node_and_message_events():
    session = client.post("/sessions/new").json()

    with client.stream(
        "POST",
        "/chat/stream",
        json={"session_id": session["session_id"], "message": "show my appointments"},
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert "event: node" in body
    assert "event: message" in body

    message_payload = None
    for block in body.strip().split("\n\n"):
        lines = block.splitlines()
        if not lines or lines[0] != "event: message":
            continue
        message_payload = json.loads(lines[1].split(": ", 1)[1])
        break

    assert message_payload is not None
    assert message_payload["current_action"] == "verify_identity"
    assert message_payload["verified"] is False
