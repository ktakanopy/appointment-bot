from fastapi.testclient import TestClient

from app.application.errors import DependencyUnavailableError
from app.api import routes
from app.main import app


client = TestClient(app)


def test_invalid_payload_returns_422():
    response = client.post("/chat", json={"session_id": "missing-message"})

    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid chat request"}


def test_repository_failure_returns_503(monkeypatch):
    def fail_run(*args, **kwargs):
        raise DependencyUnavailableError("boom")

    session = client.post("/sessions/new").json()
    monkeypatch.setattr(app.state.runtime.handle_chat_turn_use_case.workflow, "run", fail_run)

    response = client.post("/chat", json={"session_id": session["session_id"], "message": "show my appointments"})

    assert response.status_code == 503
    assert response.json() == {"detail": "The appointment service is temporarily unavailable."}
