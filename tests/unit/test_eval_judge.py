from __future__ import annotations

from app.evals.judge import run_judge
from app.evals.models import EvaluationScenario


def test_run_judge_uses_deterministic_fallback_without_provider():
    scenario = EvaluationScenario(
        scenario_id="s1",
        title="Scenario",
        input_turns=[],
        expected_outcomes={"verified": True},
        judge_rubric="Verify state",
        category="verification",
    )

    result = run_judge(None, scenario, [], {"verified": True})

    assert result.status == "pass"


def test_run_judge_returns_error_when_provider_raises():
    class BrokenProvider:
        def judge(self, scenario, transcript, observed_outcomes):
            raise RuntimeError("judge unavailable")

    scenario = EvaluationScenario(
        scenario_id="s2",
        title="Scenario",
        input_turns=[],
        expected_outcomes={"verified": True},
        judge_rubric="Verify state",
        category="verification",
    )

    result = run_judge(BrokenProvider(), scenario, [], {"verified": True})

    assert result.status == "error"
