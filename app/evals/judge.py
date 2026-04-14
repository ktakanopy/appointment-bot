from __future__ import annotations

from app.evals.models import EvaluationScenario
from app.llm.schemas import JudgeResult


def run_judge(provider, scenario: EvaluationScenario, transcript: list[dict], observed_outcomes: dict) -> JudgeResult:
    try:
        return provider.judge(scenario.model_dump(), transcript, observed_outcomes)
    except Exception as error:
        return JudgeResult(status="error", summary=str(error), score=None)
