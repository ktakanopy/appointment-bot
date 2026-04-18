from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from app.evals.judge import run_judge
from app.evals.models import EvaluationResult, EvaluationScenario
from app.evals.scenarios.core_scenarios import CORE_SCENARIOS
from app.observability import set_eval_scenario
from app.responses import build_chat_response, build_response_text
from app.runtime import close_runtime, create_eval_runtime


def run_scenarios(scenarios=None) -> list[EvaluationResult]:
    scenarios = scenarios or CORE_SCENARIOS
    results = []
    for index, scenario in enumerate(scenarios, start=1):
        runtime = create_eval_runtime()
        try:
            result = run_scenario(runtime, scenario)
        finally:
            close_runtime(runtime)
        print(format_result_block(index, scenario, result))
        print()
        results.append(result)
    return results


def run_scenario(runtime, scenario: EvaluationScenario) -> EvaluationResult:
    set_eval_scenario(runtime.logger, scenario.scenario_id, scenario.title)
    transcript: list[dict[str, str]] = []
    observed_outcomes: dict[str, object] = {}

    try:
        observed_outcomes = replay_scenario(runtime, scenario, transcript)
        judged = run_judge(runtime.provider, scenario, transcript, observed_outcomes)
        return build_evaluation_result(
            scenario,
            status=judged.status,
            summary=judged.summary,
            score=judged.score,
            observed_outcomes=observed_outcomes,
            transcript=transcript,
        )
    except Exception as error:
        return build_evaluation_result(
            scenario,
            status="error",
            summary=str(error),
            score=None,
            observed_outcomes=observed_outcomes,
            transcript=transcript,
        )
    finally:
        set_eval_scenario(runtime.logger, None, None)


def replay_scenario(runtime, scenario: EvaluationScenario, transcript: list[dict[str, str]]) -> dict[str, object]:
    runtime.session_service.cleanup_expired()
    session = runtime.session_service.create_session()
    observed_outcomes: dict[str, object] = {}

    for turn in scenario.input_turns:
        observed_outcomes = replay_turn(runtime, session.thread_id, turn, transcript)

    return observed_outcomes


def replay_turn(
    runtime,
    thread_id: str,
    turn: str,
    transcript: list[dict[str, str]],
) -> dict[str, object]:
    transcript.append({"role": "user", "content": turn})
    state = runtime.workflow.run(thread_id, turn)
    response_text = build_response_text(state)
    result = build_chat_response(thread_id, response_text, state)
    transcript.append({"role": "assistant", "content": result.response})
    return extract_observed_outcomes(result)


def extract_observed_outcomes(result) -> dict[str, object]:
    return {
        "verified": result.verified,
        "current_operation": result.current_operation.value,
        "issue": result.issue,
        "last_outcome": (
            result.last_action_result.outcome.value
            if result.last_action_result is not None
            else None
        ),
    }


def build_evaluation_result(
    scenario: EvaluationScenario,
    *,
    status: str,
    summary: str,
    score: float | None,
    observed_outcomes: dict[str, object],
    transcript: list[dict[str, str]],
) -> EvaluationResult:
    return EvaluationResult(
        scenario_id=scenario.scenario_id,
        scenario_title=scenario.title,
        status=status,
        judge_summary=summary,
        score=score,
        observed_outcomes=observed_outcomes,
        input_turns=[message["content"] for message in transcript if message["role"] == "user"],
        assistant_outputs=[message["content"] for message in transcript if message["role"] == "assistant"],
        trace_id=None,
    )


def build_results_summary(results: list[EvaluationResult]) -> dict[str, float | int | None]:
    pass_count = sum(1 for result in results if result.status == "pass")
    fail_count = sum(1 for result in results if result.status == "fail")
    error_count = sum(1 for result in results if result.status == "error")
    total_count = len(results)
    pass_rate = (pass_count / total_count) if total_count else None
    return {
        "total": total_count,
        "pass": pass_count,
        "fail": fail_count,
        "error": error_count,
        "pass_rate": pass_rate,
    }


def format_results_summary(results: list[EvaluationResult]) -> str:
    summary = build_results_summary(results)
    pass_rate = summary["pass_rate"]
    pass_rate_text = f"{pass_rate * 100:.1f}%" if pass_rate is not None else "n/a"
    return "\n".join(
        [
            "=" * 80,
            "Run Summary",
            "=" * 80,
            f"Total tests   : {summary['total']}",
            f"Passed        : {summary['pass']}",
            f"Failed        : {summary['fail']}",
            f"Errors        : {summary['error']}",
            f"Pass rate     : {pass_rate_text}",
        ]
    )


def format_score(score: float | None) -> str:
    return f"{score:.2f}" if score is not None else "n/a"


def format_result_block(
    test_number: int,
    scenario: EvaluationScenario,
    result: EvaluationResult,
) -> str:
    return "\n".join(
        [
            "=" * 80,
            f"Test {test_number}: {scenario.scenario_id}",
            "=" * 80,
            f"Title            : {scenario.title}",
            f"Category         : {scenario.category}",
            f"Expected outcomes: {format_mapping(scenario.expected_outcomes)}",
            f"Judge rubric     : {scenario.judge_rubric}",
            f"Result           : {result.status}",
            f"Judge score      : {format_score(result.score)}",
            "",
            "Eval Input",
            format_input_turns(scenario.input_turns),
            "",
            "Generated Conversation",
            format_conversation(result),
            "",
            "Observed Outcomes",
            format_mapping_lines(result.observed_outcomes),
            "",
            "Judge Output",
            result.judge_summary,
        ]
    )


def format_conversation(result: EvaluationResult) -> str:
    lines: list[str] = []
    turn_count = max(len(result.input_turns), len(result.assistant_outputs))

    for index in range(turn_count):
        if index < len(result.input_turns):
            lines.append(f"{index + 1}. user: {result.input_turns[index]}")
        if index < len(result.assistant_outputs):
            lines.extend(format_bot_lines(result.assistant_outputs[index]))

    return "\n".join(lines)


def format_bot_lines(message: str) -> list[str]:
    parts = message.splitlines() or [message]
    lines = [f"   bot : {parts[0]}"]
    for part in parts[1:]:
        lines.append(f"         {part}")
    return lines


def format_input_turns(input_turns: list[str]) -> str:
    return "\n".join(
        f"- turn {index}: {turn}"
        for index, turn in enumerate(input_turns, start=1)
    )


def format_mapping(mapping: dict[str, object]) -> str:
    if not mapping:
        return "{}"
    parts = [f"{key}={value!r}" for key, value in mapping.items()]
    return "{" + ", ".join(parts) + "}"


def format_mapping_lines(mapping: dict[str, object]) -> str:
    if not mapping:
        return "- None"
    return "\n".join(f"- {key}: {value}" for key, value in mapping.items())


def main() -> None:
    results = run_scenarios()
    results_path = save_results(results)
    print(format_results_summary(results))
    print()
    print(f"Saved full results to {results_path}")


def save_results(results: list[EvaluationResult]) -> Path:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(".eval_runs") / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    results_path = run_dir / "results.json"
    results_path.write_text(
        json.dumps([result.model_dump() for result in results], ensure_ascii=True, indent=2)
        + "\n"
    )
    return results_path


if __name__ == "__main__":
    main()
