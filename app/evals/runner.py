from __future__ import annotations

import json
from uuid import uuid4

from app.api.routes import create_runtime
from app.evals.judge import run_judge
from app.evals.models import EvaluationResult
from app.evals.scenarios.core_scenarios import CORE_SCENARIOS


def run_scenarios(scenarios=None) -> list[EvaluationResult]:
    runtime = create_runtime()
    try:
        scenarios = scenarios or CORE_SCENARIOS
        results = []
        provider = runtime.provider
        for scenario in scenarios:
            session_id = f"eval-{scenario.scenario_id}-{uuid4()}"
            transcript = []
            observed_outcomes = {}
            status = "pass"
            summary = "Scenario completed."
            score = 1.0
            try:
                for turn in scenario.input_turns:
                    transcript.append({"role": "user", "content": turn})
                    result = runtime.graph.invoke(
                        {"thread_id": session_id, "incoming_message": turn},
                        {"configurable": {"thread_id": session_id}},
                    )
                    transcript.append({"role": "assistant", "content": result.get("response_text")})
                    observed_outcomes = {
                        "verified": result.get("verified", False),
                        "current_action": result.get("requested_action"),
                        "error_code": result.get("error_code"),
                        "last_outcome": (result.get("last_action_result") or {}).get("outcome"),
                    }
                judged = run_judge(provider, scenario, transcript, observed_outcomes)
                status = judged.status
                summary = judged.summary
                score = judged.score
            except Exception as error:
                status = "error"
                summary = str(error)
                score = None
            results.append(
                EvaluationResult(
                    scenario_id=scenario.scenario_id,
                    status=status,
                    judge_summary=summary,
                    score=score,
                    observed_outcomes=observed_outcomes,
                    trace_id=None,
                )
            )
        return results
    finally:
        runtime.checkpoint_connection.close()


def main() -> None:
    print(json.dumps([result.model_dump() for result in run_scenarios()], ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
