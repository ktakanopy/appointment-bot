# LLM boundary

This document describes how language models participate in the appointment bot. The runtime is designed so that correctness, authorization, and state changes do not depend on nondeterministic model output.

## 1. Design principle

The LLM is non-authoritative. It performs one product role on the live chat path:

1. **Intent extraction** — parse the user message into a structured operation label and entity fields.

Final response wording is deterministic by design (see ADR-011). `ResponsePolicy` produces the patient-facing text directly from workflow outcomes; no second model call is made to polish that text. The model does not grant or deny access, does not mutate appointments or identity state, and does not decide graph routing or response content. Those responsibilities stay in deterministic Python code paths. Security-sensitive and policy outcomes are computed from explicit rules and repository operations, not from free-form LLM text.

## 2. Provider protocol

`LLMProvider` in `app/llm/base.py` is a `Protocol` with three methods:

| Method | Role |
|--------|------|
| `interpret(message, state) -> IntentPrediction` | Propose `requested_operation`, `full_name`, `phone`, `dob`, `appointment_reference` from the message and a small state snapshot. |
| `generate_response(state, fallback_text) -> AssistantResponse` | Retained for interface completeness. Not called on the live chat path; final response wording comes from `ResponsePolicy` directly (see ADR-011). |
| `judge(scenario, transcript, observed_outcomes) -> JudgeResult` | Used by the evaluation harness; not part of the live chat graph. |

`IntentPrediction`, `AssistantResponse`, and `JudgeResult` are Pydantic models in `app/llm/schemas.py`. They constrain what the implementation may return and keep the boundary typed.

## 3. Factory pattern

`build_provider` in `app/infrastructure/llm/factory.py` constructs a concrete provider from `Settings`. It returns `OpenAIProvider` when `ProviderSettings.provider_name` is `"openai"` and `ProviderSettings.api_key` is present. Those values come from environment configuration (`LLM_PROVIDER` defaults to `openai`; `OPENAI_API_KEY` supplies the key). If configuration is missing or unsupported, the factory raises and runtime startup fails fast.

## 4. Runtime behavior

- **`interpret`** delegates action and entity extraction to the configured provider.
- **`ChatResponseService.generate()`** returns the deterministic fallback text produced by `ResponsePolicy` directly. The `generate_response` provider method is not called on the live chat path (see ADR-011).
- Verification, appointment ownership, idempotency, issue classification, and workflow routing stay in deterministic Python code outside the provider.

Provider calls are no longer wrapped in local fallback logic. If the provider raises, the failure propagates instead of silently degrading to deterministic behavior.

## 5. Prompt design

One system prompt, kept short and task-scoped:

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

A response prompt (`app/prompts/response_prompt.py`, `RESPONSE_PROMPT`) is defined in the codebase but is not called on the live chat path; it is retained alongside the `generate_response` interface for potential future use. `OpenAIProvider._complete` in `app/infrastructure/llm/openai_provider.py` passes `response_format={"type": "json_object"}` on chat completions so the API returns parseable JSON. The intent prompt explicitly steers the model away from authorization and policy decisions; the judge path uses its own minimal JSON instruction for eval-only calls.

## 6. LLM vs deterministic flow map

The provider is used once inside the workflow, at the interpret step. The application presentation layer is fully deterministic.

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
| `ChatResponseService.generate()` | No | Yes (ResponsePolicy produces final text; no provider call) |

## 7. Why not a ReAct agent

For this use case, a ReAct agent would give the model too much control over a workflow that is mostly policy-driven. The critical decisions are whether the patient is verified, whether an appointment belongs to that patient, whether a mutation is idempotent, and whether the session is locked. Those decisions are deterministic and easy to encode directly in Python, which makes the system easier to test, reason about, and defend against prompt-injection attempts. The chosen design keeps the model useful at the boundaries without turning it into the workflow authority.

## 8. Error isolation

Tracing failures do not abort the request path, but provider failures still do. `OpenAIProvider.interpret()` calls the provider directly, so provider exceptions surface as runtime errors. `ChatResponseService.generate()` does not call the provider and is therefore isolated from provider failures.
