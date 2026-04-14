from __future__ import annotations

from app.evals.models import EvaluationScenario
from app.llm.schemas import JudgeResult


def run_judge(provider, scenario: EvaluationScenario, transcript: list[dict], observed_outcomes: dict) -> JudgeResult:
    if provider is None:
        passed = _matches_expected_outcomes(scenario.expected_outcomes, observed_outcomes)
        return JudgeResult(
            status="pass" if passed else "fail",
            summary="Deterministic review completed without a model judge.",
            score=1.0 if passed else 0.0,
        )
    try:
        return provider.judge(scenario.model_dump(), transcript, observed_outcomes)
    except Exception as error:
        return JudgeResult(status="error", summary=str(error), score=None)


def _matches_expected_outcomes(expected_outcomes: dict, observed_outcomes: dict) -> bool:
    for key, value in expected_outcomes.items():
        if observed_outcomes.get(key) != value:
            return False
    return True
