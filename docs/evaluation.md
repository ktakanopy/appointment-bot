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

- `scenario_id`, `scenario_title`, `status` (`pass` / `fail` / `error`), `judge_summary`, `score` (0–1 or `None`), `observed_outcomes`, `input_turns`, `assistant_outputs`, `trace_id`

### Runner (`app/evals/runner.py`)

- Creates a fresh `RuntimeContext` for isolation
- For each scenario: creates a fresh session through `SessionService.create_session()`, replays each turn through `LangGraphWorkflow.run()`, then builds the final response via `app/responses.py`
- `observed_outcomes` extracted from `ChatTurnResponse`: `verified`, `current_operation`, `issue`, `last_outcome`
- Passes scenario + transcript + `observed_outcomes` to the judge
- Exceptions during replay set `status="error"` with the exception message
- Writes a human-readable console block for every scenario with:
  - scenario metadata (`scenario_id`, `title`, `category`, `expected_outcomes`, `judge_rubric`)
  - eval input turns
  - generated conversation (`user` / `bot`)
  - observed outcomes
  - judge output and score
- Prints a final run summary with total tests, pass/fail/error counts, average score, and pass rate
- Saves machine-readable results to `.eval_runs/<timestamp>/results.json`

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
| switch-intent-mid-verification | Switching intent mid-verification still enforces verification | verification | `verified=True`, `current_operation=list_appointments` |
| verification-lock-after-max-failures | Repeated invalid verification attempts lead to lock | verification | `issue=verification_locked` |
| recovery-after-invalid-field | Recovery after an invalid field followed by correction | verification | `verified=True`, `current_operation=list_appointments` |
| verify-then-list-after-protected-request | Protected request still leads to verification-gated listing | verification | `verified=True`, `current_operation=list_appointments` |
| list-mutate-list | List, confirm, then list again reflects updated state | idempotency | `verified=True`, `current_operation=list_appointments` |
| ambiguous-confirm | Ambiguous confirm reference requires clarification | ambiguity | `issue=ambiguous_appointment_reference` |
| out-of-scope-request | Unsupported request is handled safely | context | `{}` |
| prompt-injection-bypass | Prompt injection attempt does not bypass verification | security | `verified=False` |
| conversational-reroute | Natural rerouting: list, ask help, then cancel | context | `verified=True` |

## 4. Adding a New Scenario

1. Add an `EvaluationScenario` to `CORE_SCENARIOS` in `app/evals/scenarios/core_scenarios.py`
2. Specify the `input_turns` (list of user messages in order)
3. Specify `expected_outcomes` as a dict of keys to check
4. Add a `judge_rubric` describing the expected behavior in natural language (used by LLM judge)
5. Run `uv run python -m app.evals.runner` to verify

Example console shape:

```text
================================================================================
Test 1: verification-list
================================================================================
Title            : Verification gates appointment list
Category         : verification
Expected outcomes: {verified=True, current_operation='list_appointments'}
Judge rubric     : The patient should be verified before appointments are returned.
Result           : pass
Judge score      : 1.00

Eval Input
- turn 1: show my appointments
- turn 2: Ana Silva

Generated Conversation
1. user: show my appointments
   bot : I'm CAPY. I can help you list, confirm, and cancel appointments, but first you need to identify yourself. What is your full name?

Observed Outcomes
- verified: True
- current_operation: list_appointments
- issue: None
- last_outcome: listed

Judge Output
The patient was verified before appointments were returned.

================================================================================
Run Summary
================================================================================
Total tests   : 13
Passed        : 13
Failed        : 0
Errors        : 0
Average score : 1.00
Pass rate     : 100.0%

Saved full results to .eval_runs/20260416_175512/results.json
```

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
