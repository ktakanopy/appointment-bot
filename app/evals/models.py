from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class EvaluationScenario(BaseModel):
    scenario_id: str
    title: str
    input_turns: list[str]
    expected_outcomes: dict[str, Any]
    judge_rubric: str
    category: str


class EvaluationResult(BaseModel):
    scenario_id: str
    status: Literal["pass", "fail", "error"]
    judge_summary: str
    score: float | None = None
    observed_outcomes: dict[str, Any]
    trace_id: str | None = None
