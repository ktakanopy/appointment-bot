# LLM boundary

The LLM is intentionally boxed in.

That is one of the main design choices in this project. In a healthcare-adjacent
workflow, I do not want the model deciding whether a patient gets access to data
or whether a mutation should happen.

## What the model does

The live chat path uses the model for one thing:

- intent and entity extraction

More concretely, the provider returns a structured `IntentPrediction` with:

- `requested_operation`
- `full_name`
- `phone`
- `dob`
- `appointment_reference`

The eval system also uses the provider as a judge, but that is outside the live
chat workflow.

## What the model does not do

The model does not:

- decide whether the patient is verified
- decide whether an appointment belongs to the patient
- confirm or cancel appointments directly
- choose final patient-facing wording
- control the workflow once interpretation is done

Those decisions stay in deterministic Python.

## Provider surface

`OpenAIProvider` exposes two methods:

| Method | Purpose |
|---|---|
| `interpret(message, state)` | Extract structured intent and fields from the user message |
| `judge(scenario, transcript, observed_outcomes)` | Eval-only judging path |

The provider uses OpenAI structured parsing against Pydantic models in
`app/llm/schemas.py`.

## Prompt design

The prompt in `app/llm/prompt.py` is pretty strict.

It tells the model to:

- return only known operation values
- leave unknown fields as `null`
- avoid authorization or state mutation decisions
- use recent messages only to resolve the current request

That last point matters. The model can use context to understand `confirm the
first one`, but it should not invent a brand-new request from history alone.

## Failure behavior

If `interpret()` fails after retries, the workflow raises
`DependencyUnavailableError` and the API returns HTTP 503.

I left out a heuristic fallback on purpose. For this exercise, a clean failure
is better than a half-trustworthy guess.

## Why not use a ReAct agent?

Because the interesting part of this system is policy, not tool autonomy.

The model is useful at the boundary. It is not the part I want in charge.
