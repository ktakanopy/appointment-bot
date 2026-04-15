# Architecture Decision Records

## ADR-001: FastAPI as HTTP Framework

**Status:** Accepted

**Context:** The exercise requires a Python backend with an endpoint for conversational AI. FastAPI provides async support, automatic OpenAPI documentation, Pydantic integration for request/response validation, and dependency injection.

**Decision:** Use FastAPI with Pydantic models and `Depends` for runtime injection.

**Consequences:** Swagger UI is available out of the box. Pydantic `extra="forbid"` catches unexpected fields early. The lifespan context manager handles startup and shutdown cleanly.

## ADR-002: LangGraph StateGraph for Workflow

**Status:** Accepted

**Context:** The conversation requires multi-step flows (verification then action) with conditional routing. A ReAct-style agent would give the model more authority than this workflow needs and would mix LLM control with business logic. LangGraph's StateGraph provides explicit, inspectable, deterministic routing.

**Decision:** Use LangGraph StateGraph with typed ConversationState and pure-function routing.

**Consequences:** Routing logic is testable without an LLM. The graph can be visualized as a diagram. State mutations are explicit and auditable, and the graph is compiled once and reused across requests. The design is easier to reason about than a ReAct loop for verification-gated healthcare workflows.

## ADR-003: InMemorySaver for Conversation State

**Status:** Accepted

**Context:** The project is intentionally scoped as a demo. Persisting conversation state across restarts adds extra code and operational concerns that are not necessary to demonstrate the verification and appointment flows.

**Decision:** Use LangGraph `InMemorySaver` for thread-scoped state.

**Consequences:** The runtime is simpler and easier to explain. Conversation state is lost when the process restarts, which is acceptable for the current scope.

## ADR-004: In-Memory Domain Repositories

**Status:** Accepted

**Context:** The exercise uses demo patient and appointment data. A full database would add complexity without demonstrating the core conversational AI patterns.

**Decision:** Keep PatientRepository and AppointmentRepository as in-memory implementations with hardcoded seed data. Use Protocol-based ports so implementations can be swapped.

**Consequences:** Patient and appointment data resets on restart. The Protocol pattern means production implementations can be added without changing domain or graph code.

## ADR-005: LLM as Non-Authoritative Boundary

**Status:** Accepted

**Context:** In a healthcare context, the LLM must not control access to patient data or appointment mutations. Prompt injection and hallucination are real risks.

**Decision:** Limit the LLM to intent extraction. All authorization, routing, state mutation, and response wording logic is deterministic Python, while a configured provider is required for runtime startup (see ADR-011 for the response-wording rationale).

**Consequences:** The system cannot be prompt-injected into skipping verification. Startup now fails fast when provider configuration is missing or invalid. Provider call failures surface as runtime errors instead of silently degrading to deterministic responses.

## ADR-006: In-Memory Remembered Identity Store

**Status:** Accepted

**Context:** Remembered identity has a different lifecycle than conversation state and still needs TTL and revocation semantics. For the current scope, a separate in-memory repository keeps those concerns isolated without adding persistence complexity.

**Decision:** Use a dedicated in-memory repository for remembered identity records.

**Consequences:** Revocation and restore logic stay separate from the graph state. Remembered identities are cleared on process restart, which is acceptable for the current demo scope.

## ADR-007: Streamlit Frontend

**Status:** Accepted

**Context:** The exercise asks for a backend service, but a chat UI demonstrates the conversational experience. A full React or Vue frontend would be disproportionate to the exercise scope.

**Decision:** Use Streamlit for a lightweight chat interface that calls the backend over HTTP.

**Consequences:** The frontend is a single file. It supports session management, remembered identity, and the full protected appointment flow. It is not production-grade but demonstrates the end-to-end flow.

## ADR-008: Custom Eval Runner

**Status:** Accepted

**Context:** The project needs to verify multi-turn conversation correctness. External eval frameworks (for example DeepEval or Ragas) add heavy dependencies and opinions. The eval requirements are narrow: replay turns and check outcomes.

**Decision:** Build a minimal eval runner with deterministic and LLM-as-judge modes.

**Consequences:** Evals run in pytest with no external dependencies. New scenarios are added as Python objects. The judge mode is configurable based on whether a provider is available.

## ADR-009: Session Registry with TTL

**Status:** Accepted

**Context:** Without session validation, any arbitrary string could be used as a session_id, creating orphaned state and potential security issues.

**Decision:** Require session creation via `/sessions/new` and validate session_id on every `/chat` request. Apply a TTL to expire idle sessions.

**Consequences:** Unknown session_ids return 404. Session cleanup happens lazily on each request. The registry is in-memory, so sessions are lost on restart, which is acceptable for demo scope.

## ADR-010: Verification Lockout

**Status:** Accepted

**Context:** Without attempt limits, an attacker could brute-force identity verification by trying different name, phone, and date-of-birth combinations. In a healthcare context this is a real risk.

**Decision:** Cap verification attempts per session (default 3). After the limit, lock the session permanently. The patient must start a new session.

**Consequences:** Brute-force attempts are bounded per session. The lockout is stored in ConversationState so it persists across the session. Legitimate patients who mistype can retry up to the limit or start a new session.

## ADR-011: Deterministic Final Responses

**Status:** Accepted

**Context:** The original design passed a deterministic fallback string through `ChatResponseService.generate()`, which forwarded it to the LLM for response polishing before returning the patient-facing text. While this produced slightly more natural wording, it introduced a second LLM call on every turn—after the intent extraction call—adding latency, cost, and an extra failure surface. For a healthcare appointment bot the business rules and workflow outcomes are fully enumerated and the set of patient-facing messages is small and predictable. The LLM adds the most value at the input boundary, where free-form natural language must be mapped to structured intents and entities. At the output boundary, policy-driven templates already cover every outcome and their wording is straightforward enough that LLM rewriting provides negligible quality lift.

**Decision:** Treat the deterministic fallback text produced by `ResponsePolicy` as the final response. The `generate_response` path in `LLMProvider` is retained for interface completeness but the application no longer routes live chat turns through it. The LLM is used for intent and entity extraction only.

**Consequences:**

- **Lower latency.** Each turn now makes one LLM call instead of two, halving the serial model-call depth on the hot path.
- **Lower cost.** Eliminating the response-polishing call removes a billable completion on every turn.
- **Lower complexity.** `ChatResponseService` reduces to a thin wrapper around `ResponsePolicy`. There is no prompt to maintain, no JSON schema to parse, and no provider dependency at the presentation layer.
- **Easier testing.** Response content is deterministic, so unit and integration tests can use exact-match assertions instead of semantic checks or LLM-as-judge evaluation.
- **Smaller failure surface.** A provider timeout, rate-limit, or malformed response on the polishing call can no longer degrade or abort a chat turn. Provider failures are now confined to the intent extraction step where the LLM is genuinely necessary.
- **Sufficient quality.** The appointment domain is narrow and the patient-facing messages are short and formulaic. Deterministic templates cover every outcome and meet the quality bar for this scope without model assistance.
- **LLM boundary is preserved where it matters.** Intent and entity extraction remain model-driven. The workflow, authorization, routing, and response wording all stay in deterministic Python, which is the correct layering for a policy-driven healthcare workflow.
