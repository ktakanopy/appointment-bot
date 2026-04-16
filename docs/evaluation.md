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

### EvaluationResult (`app/evals/models.py`)

Pydantic model with fields:

- `scenario_id`, `status` (`pass` / `fail` / `error`), `judge_summary`, `score` (0–1 or `None`), `observed_outcomes`, `trace_id`

### Runner (`app/evals/runner.py`)

- Creates a fresh `RuntimeContext` via `create_runtime()` for isolation
- For each scenario: creates a fresh session through `SessionService.create_session()`, replays each turn through `LangGraphWorkflow.run()`, then builds the final response via `app/responses.py`
- `observed_outcomes` extracted: `verified`, `current_operation`, `issue`, `last_outcome`
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

## 7. Intent/Entity Regression

### Purpose

The multi-turn judge scenarios validate full conversational behavior end to end. A complementary **intent/entity regression** layer validates the *structured output* of the interpretation step in isolation: given a user utterance and conversation state, does the interpret + normalize pipeline return the expected `requested_operation`, `full_name`, `phone`, `dob`, and `appointment_reference`?

This protects against drift after prompt, parser, provider, or model changes without requiring a full conversation replay.

### How it differs from the LLM-as-judge flow

| | Intent/entity regression | Multi-turn judge scenarios |
|---|---|---|
| Scope | Single interpret call | Full conversation (multiple turns) |
| Assertion style | Deterministic field comparison | LLM judge rubric evaluation |
| Speed | Fast, no conversation state | Slower, full workflow per scenario |
| What it catches | Parsing/extraction/normalization drift | Policy, flow, recovery, and clarification issues |

### Dataset

A small curated dataset lives at `app/evals/datasets/intent_entity_cases.jsonl`. Each line is a JSON object:

```json
{
  "id": "list-happy",
  "utterance": "show my appointments",
  "state": {},
  "expected": {
    "requested_operation": "list_appointments",
    "full_name": null,
    "phone": null,
    "dob": null,
    "appointment_reference": null
  }
}
```

- `utterance` — the user message to interpret.
- `state` — optional conversation state passed to the provider (defaults to `{}`).
- `expected` — a dict of fields to assert. Only listed keys are checked, so partial expected dicts are fine.

The dataset is intentionally small (~25-30 cases) and covers a practical spread of operations, entity variants, formatting, synonyms, ordinals, and edge cases. It should grow incrementally as new patterns or regressions are discovered.

### Normalization reuse

The regression test applies the same normalization functions used in production (`app/graph/parsing.py`). This ensures the test validates real normalized behaviour, not a duplicated approximation.

### Running

```bash
pytest tests/evals/test_intent_entity_regression.py -v
```

The test is parametrized: one test case per dataset row, with the case `id` as the pytest ID.
