from __future__ import annotations

import json

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
                "response": "New session started.",
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
                "current_action": "help",
                "thread_id": "s1",
                "appointments": None,
                "last_action_result": None,
                "error_code": None,
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


def test_frontend_client_reads_stream_events():
    payload = (
        "event: node\n"
        f"data: {json.dumps({'node': 'generate_response'})}\n\n"
        "event: message\n"
        f"data: {json.dumps({'response': 'Hello'})}\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/chat/stream"
        return httpx.Response(200, text=payload)

    client = BackendClient(
        "http://example.test",
        client=httpx.Client(transport=httpx.MockTransport(handler), base_url="http://example.test"),
    )

    events = list(client.send_message_stream("s1", "hello"))

    assert events == [
        {"event": "node", "data": {"node": "generate_response"}},
        {"event": "message", "data": {"response": "Hello"}},
    ]
