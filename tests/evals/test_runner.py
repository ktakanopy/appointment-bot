from __future__ import annotations

from app.evals.runner import run_scenarios


def test_eval_runner_returns_results_for_default_scenarios():
    results = run_scenarios()

    assert results
    assert {result.scenario_id for result in results} >= {
        "verification-list",
        "ambiguous-cancel",
        "idempotent-confirm",
        "retry-after-failed-verification",
        "confirm-without-list-context",
    }
