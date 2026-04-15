from __future__ import annotations

from typing import Any

import httpx


class BackendClient:
    def __init__(self, base_url: str, timeout: float = 20.0, client: httpx.Client | None = None):
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(base_url=self.base_url, timeout=timeout)

    def create_session(self) -> dict[str, Any]:
        response = self._client.post("/sessions/new")
        response.raise_for_status()
        return response.json()

    def send_message(
        self,
        session_id: str,
        message: str,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"session_id": session_id, "message": message}
        response = self._client.post("/chat", json=payload)
        response.raise_for_status()
        return response.json()
