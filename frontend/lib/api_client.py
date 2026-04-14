from __future__ import annotations

import json
from typing import Any

import httpx


class BackendClient:
    def __init__(self, base_url: str, timeout: float = 20.0, client: httpx.Client | None = None):
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(base_url=self.base_url, timeout=timeout)

    def create_session(self, remembered_identity_id: str | None = None) -> dict[str, Any]:
        payload = {}
        if remembered_identity_id:
            payload["remembered_identity_id"] = remembered_identity_id
        response = self._client.post("/sessions/new", json=payload or None)
        response.raise_for_status()
        return response.json()

    def send_message(
        self,
        session_id: str,
        message: str,
        remembered_identity_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"session_id": session_id, "message": message}
        if remembered_identity_id:
            payload["remembered_identity_id"] = remembered_identity_id
        response = self._client.post("/chat", json=payload)
        response.raise_for_status()
        return response.json()

    def send_message_stream(
        self,
        session_id: str,
        message: str,
        remembered_identity_id: str | None = None,
    ):
        payload: dict[str, Any] = {"session_id": session_id, "message": message}
        if remembered_identity_id:
            payload["remembered_identity_id"] = remembered_identity_id
        with self._client.stream("POST", "/chat/stream", json=payload) as response:
            response.raise_for_status()
            event_name = "message"
            for line in response.iter_lines():
                if not line:
                    continue
                if line.startswith("event:"):
                    event_name = line.split(":", 1)[1].strip()
                    continue
                if not line.startswith("data:"):
                    continue
                yield {
                    "event": event_name,
                    "data": json.loads(line.split(":", 1)[1].strip()),
                }

    def forget_remembered_identity(self, remembered_identity_id: str) -> dict[str, Any]:
        response = self._client.post(
            "/remembered-identity/forget",
            json={"remembered_identity_id": remembered_identity_id},
        )
        response.raise_for_status()
        return response.json()
