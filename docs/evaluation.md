# Evaluation framework

## 1. Overview

The project includes a lightweight in-repo evaluation framework instead of adopting an external eval tool. It runs multi-turn conversation scenarios against the compiled graph and uses the configured LLM provider as the judge.

## 2. Framework Components

### EvaluationScenario (`app/evals/models.py`)

Pydantic model with fields:

- `scenario_id`: unique identifier
- `title`: human-readable description
- `input_turns`: list of user messages to replay in sequence
- `expected_outcomes`: dict of key-value pairs to check against observed outcomes
- `judge_rubric`: natural language description for the LLM judge
- `category`: grouping label (`verification`, `ambiguity`, `idempotency`, `context`)

### EvaluationResult (`app/evals/models.py`)

Pydantic model with fields:

- `scenario_id`, `status` (`pass` / `fail` / `error`), `judge_summary`, `score` (0–1 or `None`), `observed_outcomes`, `trace_id`

### Runner (`app/evals/runner.py`)

- Creates a fresh `RuntimeContext` via `create_runtime()` for isolation
- For each scenario: creates a unique id `eval-{scenario_id}-{uuid}` (used as `thread_id` in `graph.invoke` config), replays each turn via `graph.invoke`, collects the transcript and `observed_outcomes` from the final turn
- `observed_outcomes` extracted: `verified`, `current_action` (from `requested_action`), `error_code`, `last_outcome` (from `last_action_result.outcome`)
- Passes scenario + transcript + `observed_outcomes` to the judge
- Exceptions during replay set `status="error"` with the exception message

### Judge (`app/evals/judge.py`)

Judge mode:

1. **LLM-as-judge**: Calls `provider.judge(scenario.model_dump(), transcript, observed_outcomes)`, which sends the full context to the LLM asking for JSON with status, summary, and score. Exceptions return `status="error"`.

## 3. Core Scenarios

Current scenarios in `app/evals/scenarios/core_scenarios.py`:

| ID | Title | Category | Expected |
|----|-------|----------|----------|
| verification-list | Verification gates appointment list | verification | `verified=True`, `current_action=list_appointments` |
| ambiguous-cancel | Ambiguous cancellation asks for clarification | ambiguity | `error_code=ambiguous_appointment_reference` |
| idempotent-confirm | Repeated confirm remains idempotent | idempotency | `last_outcome=already_confirmed` |
| retry-after-failed-verification | Retry after failed verification can recover | verification | `verified=True`, `current_action=list_appointments` |
| confirm-without-list-context | Confirm without prior list asks for context | context | `error_code=missing_list_context` |

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

Each eval run creates its own `RuntimeContext` with a fresh SQLite checkpoint database. Each scenario gets a unique thread id (`eval-{id}-{uuid}`) so conversations never cross-contaminate. The runtime is closed after all scenarios complete.
