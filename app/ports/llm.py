from __future__ import annotations

from typing import Any, Protocol

from app.llm.schemas import IntentPrediction


class LLMProvider(Protocol):
    def interpret(self, message: str, state: dict[str, Any]) -> IntentPrediction: ...
