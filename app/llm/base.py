from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from app.llm.schemas import IntentPrediction, JudgeResult


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    def interpret(self, message: str, state: dict[str, Any]) -> IntentPrediction:
        ...

    def judge(self, scenario: dict[str, Any], transcript: list[dict[str, Any]], observed_outcomes: dict[str, Any]) -> JudgeResult:
        ...
