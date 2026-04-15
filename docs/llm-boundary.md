# LLM boundary

This document describes how language models participate in the appointment bot. The runtime is designed so that correctness, authorization, and state changes do not depend on nondeterministic model output.

## 1. Design principle

The LLM is non-authoritative. It performs exactly one product role:

1. **Intent extraction** — parse the user message into a structured operation label and entity fields.

The model does not grant or deny access, does not mutate appointments or identity state, and does not decide graph routing. Final patient-facing response wording is produced deterministically by `ResponsePolicy` and is not rewritten by the model. Security-sensitive and policy outcomes are computed from explicit rules and repository operations, not from free-form LLM text.

## 2. Provider protocol

`LLMProvider` in `app/llm/base.py` is a `Protocol` with two methods:

| Method | Role |
|--------|------|
| `interpret(message, state) -> IntentPrediction` | Propose `requested_operation`, `full_name`, `phone`, `dob`, `appointment_reference` from the message and a small state snapshot. |
| `judge(scenario, transcript, observed_outcomes) -> JudgeResult` | Used by the evaluation harness; not part of the live chat graph. |

`IntentPrediction` and `JudgeResult` are Pydantic models in `app/llm/schemas.py`. They constrain what the implementation may return and keep the boundary typed.

## 3. Factory pattern

`build_provider` in `app/infrastructure/llm/factory.py` constructs a concrete provider from `Settings`. It returns `OpenAIProvider` when `ProviderSettings.provider_name` is `"openai"` and `ProviderSettings.api_key` is present. Those values come from environment configuration (`LLM_PROVIDER` defaults to `openai`; `OPENAI_API_KEY` supplies the key). If configuration is missing or unsupported, the factory raises and runtime startup fails fast.

## 4. Runtime behavior

- **`interpret`** delegates action and entity extraction to the configured provider.
- **`ChatResponseService.generate()`** returns the deterministic `ResponsePolicy` output directly. No provider call is made for response rendering.
- Verification, appointment ownership, idempotency, issue classification, and workflow routing stay in deterministic Python code outside the provider.

## 5. Prompt design

One system prompt for the live chat graph:

**Intent** (`app/prompts/intent_prompt.py`, `INTENT_PROMPT`):

```text
Return strict JSON with keys requested_operation, full_name, phone, dob, appointment_reference.
Use only these requested_operation values:
- verify_identity
- list_appointments
- confirm_appointment
- cancel_appointment
- help
- unknown
Do not decide authorization or mutate appointment state.
Leave unknown fields as null.
If the message asks to confirm or cancel an appointment by number, treat the number as patient-facing and 1-indexed.
```

`OpenAIProvider._complete` in `app/infrastructure/llm/openai_provider.py` passes `response_format={"type": "json_object"}` on chat completions so the API returns parseable JSON. The intent prompt explicitly steers the model away from authorization and policy decisions; the judge path uses its own minimal JSON instruction for eval-only calls.

## 6. LLM vs deterministic flow map

The provider is called once per turn, inside the workflow boundary.

```mermaid
flowchart LR
  subgraph workflow [Workflow]
    interpret[interpret]
    verify[verify]
    execute[execute_action]
  end
  subgraph application [Application]
    responseService[ChatResponseService.generate]
  end
```

| Stage | LLM | Deterministic |
|------|-----|---------------|
| `interpret` | Yes | No |
| `verify` | No | Yes |
| `execute_action` | No | Yes |
| `ChatResponseService.generate()` | No | Yes (`ResponsePolicy` output) |

## 7. Why not a ReAct agent

For this use case, a ReAct agent would give the model too much control over a workflow that is mostly policy-driven. The critical decisions are whether the patient is verified, whether an appointment belongs to that patient, whether a mutation is idempotent, and whether the session is locked. Those decisions are deterministic and easy to encode directly in Python, which makes the system easier to test, reason about, and defend against prompt-injection attempts. The chosen design keeps the model useful at the boundaries without turning it into the workflow authority.

## 8. Error isolation

Tracing failures do not abort the request path, but provider failures do. `OpenAIProvider.interpret()` is the only provider call in the live chat path, so provider exceptions surface as runtime errors on the interpret step only. Response rendering cannot produce provider errors because it is fully deterministic.
