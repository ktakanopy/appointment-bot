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

**Decision:** Limit the LLM to intent extraction at the workflow boundary. All authorization, routing, state mutation, and final response wording are deterministic Python. A configured provider is required for runtime startup.

**Consequences:** The system cannot be prompt-injected into skipping verification. Startup now fails fast when provider configuration is missing or invalid. Provider call failures surface as runtime errors on the interpret step. Final responses are produced by `ResponsePolicy` and are never affected by provider failures.

## ADR-006: Remembered Identity Deferred From Delivered Scope

**Status:** Superseded

**Context:** A remembered-identity layer was explored during implementation, but it expanded the delivery beyond the core hiring exercise. The main value of the submission is the verification-gated appointment flow inside a single session.

**Decision:** Remove remembered identity from the active product and keep it only as a possible future improvement.

**Consequences:** The delivered codebase is smaller and easier to explain. Session creation stays simple, there is no restore/revoke API surface, and cross-session convenience is intentionally out of scope for now.

## ADR-007: Streamlit Frontend

**Status:** Accepted

**Context:** The exercise asks for a backend service, but a chat UI demonstrates the conversational experience. A full React or Vue frontend would be disproportionate to the exercise scope.

**Decision:** Use Streamlit for a lightweight chat interface that calls the backend over HTTP.

**Consequences:** The frontend is a single file. It supports session management and the full protected appointment flow. It is not production-grade but demonstrates the end-to-end flow.

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

**Context:** The initial design used the LLM to rewrite deterministic fallback text into "polished" patient-facing wording (`generate_response`). The `ResponsePolicy` already produces complete, correct responses for every workflow outcome, making the rewrite step redundant for this use case. Adding an LLM call at the presentation layer introduces nondeterminism, extra latency, extra cost, an additional failure surface, and test complexity without a meaningful quality benefit in a tightly scoped exercise.

**Decision:** Remove `generate_response` from the `LLMProvider` protocol and `OpenAIProvider`. `ChatResponseService.generate()` returns the `ResponsePolicy` output directly. The LLM is retained only for intent and entity extraction at the workflow boundary.

**Consequences:**
- **Lower complexity:** `ChatResponseService` becomes a one-liner; no LLM call or provider dependency in the presentation layer.
- **Lower latency:** Every chat turn saves one full LLM round-trip.
- **Lower cost:** One fewer provider call per turn.
- **Easier testing:** Response tests assert against exact, deterministic strings without mocking a provider.
- **Less failure surface:** Provider errors can no longer occur during response rendering; the only provider call remaining is `interpret`.
- **Sufficient quality:** `ResponsePolicy` strings are concise, patient-facing, and correct for every workflow outcome. LLM rewriting added stylistic variation without improving accuracy or safety.
- **LLM boundary preserved:** The model still handles the intent and entity extraction task where nondeterminism is unavoidable and valuable. The workflow and all policy outcomes remain fully deterministic Python.

## ADR-012: Keep One Action Per Turn for This Delivery

**Status:** Accepted

**Context:** During review of the conversational UX, two improvements emerged as high-value and low-risk for the exercise: automatically listing appointments right after successful verification, and fixing stale appointment-reference reuse between turns. A third idea also emerged: supporting compound messages such as `confirm the first and cancel the second`. Although desirable, that behavior would expand the current design from one primary action per turn to multiple ordered actions in a single turn. The current workflow, turn state, and response contract are intentionally modeled around one interpreted operation and one main action result per message.

**Decision:** For this hiring-process delivery, keep the system scoped to one primary appointment action per user turn. Prioritize the post-verification auto-list improvement and the appointment-reference bug fix. Treat support for multiple appointment mutations in one message as a future enhancement rather than part of the current refactor.

**Consequences:** The delivered flow stays simpler, more testable, and easier to explain in review. It remains aligned with the exercise's core goals: verification-gated access, natural rerouting between turns, and deterministic protected operations. Compound commands are a known limitation for now because supporting them correctly would require widening the intent schema, turn-level workflow state, mutation execution flow, and possibly the public response contract.
