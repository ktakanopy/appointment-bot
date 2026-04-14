from __future__ import annotations

from typing import Any, Protocol

from app.llm.schemas import AssistantResponse, IntentPrediction, JudgeResult


class LLMProvider(Protocol):
    name: str

    def interpret(self, message: str, state: dict[str, Any]) -> IntentPrediction:
        ...

    def generate_response(self, state: dict[str, Any], fallback_text: str) -> AssistantResponse:
        ...

    def judge(self, scenario: dict[str, Any], transcript: list[dict[str, Any]], observed_outcomes: dict[str, Any]) -> JudgeResult:
        ...
