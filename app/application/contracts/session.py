from __future__ import annotations

from pydantic import BaseModel


class SessionRecord(BaseModel):
    session_id: str
    thread_id: str
    created_at: float
    last_seen_at: float
