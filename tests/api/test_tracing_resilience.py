from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import routes
from app.main import app


client = TestClient(app)


class BrokenTracer:
    def create_event(self, **kwargs):
        raise RuntimeError("trace down")


def test_chat_flow_succeeds_when_tracing_backend_fails():
    routes.reset_runtime(app)
    app.state.runtime.tracer = BrokenTracer()
    session = client.post("/sessions/new").json()

    response = client.post(
        "/chat",
        json={"session_id": session["session_id"], "message": "show my appointments"},
    )

    assert response.status_code == 200
