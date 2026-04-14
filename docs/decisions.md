# Architecture Decision Records

## ADR-001: FastAPI as HTTP Framework

**Status:** Accepted

**Context:** The exercise requires a Python backend with an endpoint for conversational AI. FastAPI provides async support, automatic OpenAPI documentation, Pydantic integration for request/response validation, and dependency injection.

**Decision:** Use FastAPI with Pydantic models and `Depends` for runtime injection.

**Consequences:** Swagger UI is available out of the box. Pydantic `extra="forbid"` catches unexpected fields early. The lifespan context manager handles startup and shutdown cleanly.

## ADR-002: LangGraph StateGraph for Workflow

**Status:** Accepted

**Context:** The conversation requires multi-step flows (verification then action) with conditional routing. Raw LangChain agents would mix LLM control with business logic. LangGraph's StateGraph provides explicit, inspectable, deterministic routing.

**Decision:** Use LangGraph StateGraph with typed ConversationState and pure-function routing.

**Consequences:** Routing logic is testable without an LLM. The graph can be visualized as a diagram. State mutations are explicit and auditable, and the graph is compiled once and reused across requests.

## ADR-003: SQLite Checkpoints over InMemorySaver

**Status:** Accepted

**Context:** LangGraph requires a checkpointer for thread-scoped state persistence. InMemorySaver loses state on restart. SQLite provides durable persistence without requiring a separate database server.

**Decision:** Use langgraph-checkpoint-sqlite with SqliteSaver.

**Consequences:** Conversation state survives process restarts. The checkpoint file is a single SQLite database. `check_same_thread=False` is required for multi-threaded access from async handlers.

## ADR-004: In-Memory Domain Repositories

**Status:** Accepted

**Context:** The exercise uses demo patient and appointment data. A full database would add complexity without demonstrating the core conversational AI patterns.

**Decision:** Keep PatientRepository and AppointmentRepository as in-memory implementations with hardcoded seed data. Use Protocol-based ports so implementations can be swapped.

**Consequences:** Patient and appointment data resets on restart. The Protocol pattern means production implementations can be added without changing domain or graph code.

## ADR-005: LLM as Non-Authoritative Boundary

**Status:** Accepted

**Context:** In a healthcare context, the LLM must not control access to patient data or appointment mutations. Prompt injection and hallucination are real risks.

**Decision:** Limit the LLM to intent extraction and response polishing. All authorization, routing, and state mutation logic is deterministic Python. The system works fully without an LLM.

**Consequences:** The system cannot be prompt-injected into skipping verification. Tests run without an API key. Provider failures degrade to deterministic responses rather than crashing.

## ADR-006: Separate SQLite Store for Remembered Identity

**Status:** Accepted

**Context:** Remembered identity has a different lifecycle than conversation state. It needs TTL, revocation, and cross-session lookup by patient_id. Storing it in the LangGraph checkpointer would conflate concerns.

**Decision:** Use a separate SQLite database with a dedicated repository for remembered identity records.

**Consequences:** Identity records persist independently of conversation threads. Revocation is immediate. The schema can evolve independently of the checkpointer format.

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
