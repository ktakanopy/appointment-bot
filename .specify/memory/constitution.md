<!--
Sync Impact Report
Version change: template -> 1.0.0
Modified principles:
- [PRINCIPLE_1_NAME] -> I. Deterministic Safety Gates
- [PRINCIPLE_2_NAME] -> II. Explicit Thread-Scoped Workflow State
- [PRINCIPLE_3_NAME] -> III. Bounded AI Responsibility
- [PRINCIPLE_4_NAME] -> IV. Testable Domain and Orchestration Boundaries
- [PRINCIPLE_5_NAME] -> V. Auditability, Privacy, and Idempotent Mutations
Added sections:
- Operational Boundaries
- Delivery Workflow & Quality Gates
Removed sections:
- None
Templates requiring updates:
- ✅ updated .specify/templates/plan-template.md
- ✅ updated .specify/templates/spec-template.md
- ✅ updated .specify/templates/tasks-template.md
- ⚠ pending .specify/templates/commands/*.md (directory not present in this initialized repo)
Follow-up TODOs:
- None
-->

# Appointment Bot Constitution

## Core Principles

### I. Deterministic Safety Gates
Protected appointment actions MUST remain blocked until the backend verifies the
patient's full name, phone number, and date of birth. Appointment listing,
confirmation, and cancellation MUST be enforced by deterministic policy code,
not by prompt wording or model judgment. Every confirmation or cancellation
MUST also validate appointment ownership and current status before mutation.

Rationale: this system handles sensitive patient workflows. Authorization must
be predictable, auditable, and safe under retries.

### II. Explicit Thread-Scoped Workflow State
The service MUST model conversation as explicit workflow state that includes, at
minimum, verification progress, verified identity, requested action,
deferred action, selected appointment context, and the last action result.
Each request MUST map the caller's session identifier to a stable thread
identifier and use checkpoint-backed short-term memory so multi-turn flows can
resume safely. When a protected action is requested before verification, the
system MUST preserve that intent and resume it only after verification succeeds.

Rationale: this is a controlled conversational workflow, not stateless chat.
Recoverability and rerouting depend on explicit, persisted state.

### III. Bounded AI Responsibility
The LLM MAY infer intent, extract fields from natural language, and generate
user-facing responses. The LLM MUST NOT decide whether a patient is authorized,
which patient record matches partial identity data, whether an appointment is
owned by the caller, or whether a protected mutation may proceed. If model
output is ambiguous or low-confidence, the system MUST fall back to a
deterministic clarification step and MUST NOT mutate state.

Rationale: natural language improves usability, but access control and mutation
safety cannot be probabilistic.

### IV. Testable Domain and Orchestration Boundaries
API transport, workflow orchestration, domain services, and repository access
MUST remain separate so protected behavior can be tested without relying on live
LLM calls. Every feature that touches verification, routing, or appointment
mutations MUST include automated coverage for policy gates, deferred intent
resumption, ownership checks, rerouting, failure handling, and safe retry or
idempotency behavior.

Rationale: senior-level quality in this repo comes from proving controlled
behavior under normal, ambiguous, and failing conditions.

### V. Auditability, Privacy, and Idempotent Mutations
Each conversational turn MUST emit structured logs or traces that make state
transitions inspectable, including thread identifier, node or step name,
detected intent, verification status, policy decision, action outcome, and
error code when present. Logs MUST minimize raw PII and MUST avoid exposing
information that could reveal whether another patient's records exist.
Confirmation and cancellation flows MUST be idempotent and return stable
responses when users repeat messages or clients retry requests.

Rationale: transactional conversational systems must be debuggable and safe
without leaking sensitive data.

## Operational Boundaries

The default architecture for this repository is a Python FastAPI backend that
uses LangGraph StateGraph for workflow orchestration, thread-scoped checkpoints
for short-term conversational memory, and repository interfaces to isolate
domain logic from storage.

- In scope for v1: conversational verification, appointment listing,
  confirmation, cancellation, natural rerouting, structured observability,
  in-memory or fake repositories, and detailed automated tests.
- Out of scope for v1: production-grade authentication such as OTP or MFA,
  cross-session long-term memory, real EHR or EMR integration, human handoff,
  payments, insurance workflows, and compliance claims beyond prototype
  privacy discipline.
- External integrations MUST be introduced behind interfaces and justified in
  the implementation plan.
- Persistent storage or long-term memory MAY be added later, but only when the
  plan explains why thread-scoped checkpoints and in-memory repositories are no
  longer sufficient.

## Delivery Workflow & Quality Gates

- Every specification MUST describe protected actions, verification inputs,
  deferred intent behavior, rerouting expectations, ambiguity handling,
  ownership checks, idempotency expectations, and failure recovery.
- Every implementation plan MUST pass a constitution check that confirms
  deterministic access gates, explicit state design, bounded LLM behavior,
  observability requirements, and test coverage for protected flows.
- Every task list for protected behavior MUST include unit, graph, and API
  validation for verification gating, state transitions, appointment ownership,
  idempotent mutations, and repository or parsing failures.
- Code review MUST reject prompt-only safety controls, hidden state mutation,
  or logging that captures unnecessary patient data.
- Significant architectural deviations from FastAPI + LangGraph + explicit
  state routing MUST be justified in writing before implementation begins.

## Governance

This constitution supersedes ad hoc implementation shortcuts, prompt-only
policies, and undocumented workflow behavior for this repository.

- Amendments MUST update this file, include a sync impact report, and propagate
  required changes to dependent templates or guidance in the same change.
- Versioning follows semantic versioning for governance:
  MAJOR for incompatible principle changes or removals,
  MINOR for new principles or materially expanded governance,
  PATCH for clarifications and wording improvements.
- Compliance review is mandatory for every plan, task list, and code review.
  Reviewers MUST verify that protected actions remain deterministically gated,
  logs remain privacy-aware, and required automated tests exist before merge.
- If a change cannot satisfy the constitution immediately, the blocking gap MUST
  be documented explicitly and approved before implementation continues.

**Version**: 1.0.0 | **Ratified**: 2026-04-13 | **Last Amended**: 2026-04-13
