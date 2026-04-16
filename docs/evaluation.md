# Evaluation framework

## 1. Overview

The project includes a lightweight in-repo evaluation framework instead of an external eval tool. It runs multi-turn conversation scenarios through the runtime/workflow boundary and uses the configured LLM provider as judge.

## 2. Framework Components

### EvaluationScenario (`app/evals/models.py`)

Pydantic model with fields:

- `scenario_id`: unique identifier
- `title`: human-readable description
- `input_turns`: list of user messages to replay in sequence
- `expected_outcomes`: dict of key-value pairs to check against observed outcomes
- `judge_rubric`: natural language description for the LLM judge
- `category`: grouping label (`verification`, `ambiguity`, `idempotency`, `context`)

`expected_outcomes` is intended to mirror the small subset of outcome fields the
eval runner extracts from `ChatTurnResponse`, not the full response model. In
practice that means scenario authors usually express expectations using the same
shape as `observed_outcomes`, such as:

- `verified`
- `current_operation`
- `issue`
- `last_outcome`

Those fields come from `ChatTurnResponse.verified`,
`ChatTurnResponse.current_operation`, `ChatTurnResponse.issue`, and
`ChatTurnResponse.last_action_result.outcome` respectively.

### EvaluationResult (`app/evals/models.py`)

Pydantic model with fields:

- `scenario_id`, `status` (`pass` / `fail` / `error`), `judge_summary`, `score` (0–1 or `None`), `observed_outcomes`, `trace_id`

### Runner (`app/evals/runner.py`)

- Creates a fresh `RuntimeContext` for isolation
- For each scenario: creates a fresh session through `SessionService.create_session()`, replays each turn through `LangGraphWorkflow.run()`, then builds the final response via `app/responses.py`
- `observed_outcomes` extracted from `ChatTurnResponse`: `verified`, `current_operation`, `issue`, `last_outcome`
- Passes scenario + transcript + `observed_outcomes` to the judge
- Exceptions during replay set `status="error"` with the exception message

### Judge (`app/evals/judge.py`)

Judge mode:

1. **LLM-as-judge**: Calls `provider.judge(scenario.model_dump(), transcript, observed_outcomes)`, which sends the full context to the LLM asking for JSON with status, summary, and score. Exceptions return `status="error"`.

## 3. Core Scenarios

Current scenarios in `app/evals/scenarios/core_scenarios.py`:

| ID | Title | Category | Expected |
|----|-------|----------|----------|
| verification-list | Verification gates appointment list | verification | `verified=True`, `current_operation=list_appointments` |
| ambiguous-cancel | Ambiguous cancellation asks for clarification | ambiguity | `issue=ambiguous_appointment_reference` |
| idempotent-confirm | Repeated confirm remains idempotent | idempotency | `last_outcome=already_confirmed` |
| retry-after-failed-verification | Retry after failed verification can recover | verification | `verified=True`, `current_operation=list_appointments` |
| confirm-without-list-context | Confirm without prior list asks for context | context | `issue=missing_list_context` |

## 4. Adding a New Scenario

1. Add an `EvaluationScenario` to `CORE_SCENARIOS` in `app/evals/scenarios/core_scenarios.py`
2. Specify the `input_turns` (list of user messages in order)
3. Specify `expected_outcomes` as a dict of keys to check
4. Add a `judge_rubric` describing the expected behavior in natural language (used by LLM judge)
5. Run `uv run python -m app.evals.runner` to verify

## 5. Running Evals

CLI:

```bash
uv run python -m app.evals.runner
```

Via pytest:

```bash
uv run --extra dev pytest tests/evals
```

The test `test_eval_runner_returns_results_for_default_scenarios` verifies that all core scenarios produce results.

## 6. State Isolation

Each eval run creates its own `RuntimeContext` with fresh in-memory adapters. Each scenario gets a new session and thread id so conversations never cross-contaminate. The runtime is closed after all scenarios complete.
