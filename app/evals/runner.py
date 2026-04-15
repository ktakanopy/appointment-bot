from __future__ import annotations

import json

from app.evals.judge import run_judge
from app.evals.models import EvaluationResult
from app.evals.scenarios.core_scenarios import CORE_SCENARIOS
from app.responses import build_chat_response, build_response_text
from app.runtime import close_runtime, create_runtime


def run_scenarios(scenarios=None) -> list[EvaluationResult]:
    runtime = create_runtime()
    try:
        scenarios = scenarios or CORE_SCENARIOS
        results = []
        provider = runtime.provider
        for scenario in scenarios:
            transcript = []
            observed_outcomes = {}
            status = "pass"
            summary = "Scenario completed."
            score = 1.0
            try:
                runtime.session_service.cleanup_expired()
                session = runtime.session_service.create_session()
                session_id = session.session_id
                for turn in scenario.input_turns:
                    transcript.append({"role": "user", "content": turn})
                    runtime.session_service.cleanup_expired()
                    active_session = runtime.session_service.require_session(session_id)
                    state = runtime.workflow.run(active_session.thread_id, turn)
                    response_text = build_response_text(state)
                    result = build_chat_response(active_session.thread_id, response_text, state)
                    transcript.append({"role": "assistant", "content": result.response})
                    observed_outcomes = {
                        "verified": result.verified,
                        "current_operation": result.current_operation.value,
                        "issue": result.issue,
                        "last_outcome": (
                            result.last_action_result.outcome.value
                            if result.last_action_result is not None
                            else None
                        ),
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
        close_runtime(runtime)


def main() -> None:
    print(json.dumps([result.model_dump() for result in run_scenarios()], ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
