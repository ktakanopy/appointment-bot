# Evaluation framework

The repo includes a small eval runner for multi-turn scenarios.

I like this part because it checks something normal unit tests miss: whether the
assistant still behaves correctly across a whole conversation, not just inside
one function call.

## What it does

For each scenario, the runner:

1. creates a fresh runtime
2. creates a fresh session
3. replays the user turns through the real workflow
4. captures the assistant outputs and observed outcomes
5. sends the whole transcript to the judge model
6. prints a readable result block and saves JSON results under `.eval_runs/`

## Main pieces

### `EvaluationScenario`

Defined in `app/evals/models.py`.

Fields:

- `scenario_id`
- `title`
- `input_turns`
- `expected_outcomes`
- `judge_rubric`
- `category`

`expected_outcomes` is intentionally small. It mirrors the fields the runner
extracts from the final `ChatTurnResponse`, not the full response object.

In practice that usually means:

- `verified`
- `current_operation`
- `issue`
- `last_outcome`

Those fields exist because the runtime exposes a small structured summary of the
turn through `ChatTurnResponse`. That gives evals something stable to assert
against without depending on exact wording in the assistant message.

In particular:

- `issue` explains what kind of problem occurred
- `last_outcome` explains what business action actually happened

That is why the graph keeps fields like `turn.issue` and
`turn.operation_result` even though the user also receives a natural-language
response.

### `EvaluationResult`

Also defined in `app/evals/models.py`.

It stores:

- scenario metadata
- pass/fail/error status
- judge summary and score
- observed outcomes
- input turns
- assistant outputs

### Runner

Implemented in `app/evals/runner.py`.

The runner creates a fresh `RuntimeContext` per scenario, replays the turns, and
prints a readable block for each case. It also prints a final summary and writes
JSON results to `.eval_runs/<timestamp>/results.json`.

### Judge

Implemented in `app/evals/judge.py`.

The judge path uses the configured provider in eval mode only. It receives:

- the scenario
- the full transcript
- observed outcomes extracted from the actual run

If the judge call fails, the result is marked as `error`.

## Core scenarios

The default scenarios live in `app/evals/scenarios/core_scenarios.py` and cover
the cases I cared most about for this submission:

- verification before listing appointments
- ambiguous references
- idempotent confirm behavior
- retry after failed verification
- switching intent during verification
- verification lockout
- invalid field recovery
- protected request before verification
- list, mutate, list again
- prompt-injection-style bypass attempts
- conversational rerouting between actions

## Running evals

CLI:

```bash
uv run python -m app.evals.runner
```

Pytest wrapper:

```bash
uv run --extra dev pytest tests/evals
```

## Why keep this in the repo?

Because it keeps the workflow honest.

It is easy to break a multi-turn assistant in ways that unit tests do not catch.
This runner gave me a much better feel for whether the product still behaved the
way a patient would expect.
