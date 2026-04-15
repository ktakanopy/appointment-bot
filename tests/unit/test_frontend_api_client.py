from __future__ import annotations

import httpx

from frontend.lib.api_client import BackendClient


def test_frontend_client_posts_new_session_payload():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/sessions/new"
        return httpx.Response(
            200,
            json={
                "session_id": "s1",
                "thread_id": "s1",
                "restored_verification": False,
                "remembered_identity_status": {
                    "remembered_identity_id": "",
                    "status": "unavailable",
                    "display_name": None,
                    "expires_at": None,
                },
                "response": "Hello, I'm CAPY. I can help you with your appointments.",
            },
        )

    client = BackendClient(
        "http://example.test",
        client=httpx.Client(transport=httpx.MockTransport(handler), base_url="http://example.test"),
    )

    response = client.create_session()

    assert response["session_id"] == "s1"


def test_frontend_client_posts_chat_message():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/chat"
        assert request.read().decode("utf-8") == '{"session_id":"s1","message":"hello"}'
        return httpx.Response(
            200,
            json={
                "response": "Hello",
                "verified": False,
                "current_operation": "help",
                "thread_id": "s1",
                "appointments": None,
                "last_action_result": None,
                "issue": None,
                "remembered_identity_status": {
                    "remembered_identity_id": "",
                    "status": "unavailable",
                    "display_name": None,
                    "expires_at": None,
                },
            },
        )

    client = BackendClient(
        "http://example.test",
        client=httpx.Client(transport=httpx.MockTransport(handler), base_url="http://example.test"),
    )

    response = client.send_message("s1", "hello")

    assert response["response"] == "Hello"
