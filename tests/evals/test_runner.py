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
        "switch-intent-mid-verification",
        "verification-lock-after-max-failures",
        "recovery-after-invalid-field",
        "verify-then-list-after-protected-request",
        "list-mutate-list",
        "ambiguous-confirm",
        "out-of-scope-request",
        "prompt-injection-bypass",
        "conversational-reroute",
    }
