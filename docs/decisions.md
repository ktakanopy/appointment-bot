# Architecture decisions

This file is a short record of the decisions that shaped the current version of
the project. I kept it tighter than a full ADR log because this is still a
take-home, not a long-lived platform.

## 1. FastAPI for the API layer

**Status:** Accepted

**Why:** The task needs a Python HTTP service with validation and a clean review
surface. FastAPI gives request validation, OpenAPI docs, and straightforward
dependency wiring without much overhead.

**Result:** The API surface stays small: `POST /sessions/new`, `POST /chat`, and
`GET /health`.

## 2. LangGraph for workflow control

**Status:** Accepted

**Why:** The hard part of this project is multi-turn workflow, not open-ended
agent behavior. The app needs explicit transitions for identity collection,
verification, protected actions, retries, and lockout.

**Result:** The graph is inspectable, deterministic after interpretation, and
easy to test.

## 3. Keep the LLM non-authoritative

**Status:** Accepted

**Why:** In a protected appointment flow, the model should not be making access
or mutation decisions.

**Decision:** Use the LLM only for intent and entity extraction in the live chat
path. Keep routing, authorization, state changes, and final response wording in
deterministic Python.

**Result:** Prompt injection cannot bypass the verification gate just by talking
the model into it.

## 4. Deterministic final responses

**Status:** Accepted

**Why:** An earlier design considered an extra LLM step for polished response
wording. It added latency and failure surface without helping safety or
correctness.

**Decision:** Final patient-facing responses come from `app/responses.py`.

**Result:** The live request path uses one provider call per turn, not two.

## 5. SQLite checkpoints plus in-memory business data

**Status:** Accepted

**Why:** The workflow benefits from real persisted conversation state across
turns, but the exercise does not need a full database for appointments and
patients.

**Decision:** Use SQLite-backed `SqliteSaver` for LangGraph state. Keep patient,
appointment, and session repositories simple.

**Result:** The conversation flow stays stateful without turning the project into
an infrastructure exercise.

## 6. In-memory patient and appointment repositories

**Status:** Accepted

**Why:** Seeded demo data is enough to demonstrate the product behavior.

**Decision:** Keep domain repositories in memory with a small fixed dataset.

**Result:** The reviewer can understand the whole app quickly, and the core
workflow stays the focus.

## 7. Session registry with TTL

**Status:** Accepted

**Why:** Letting any arbitrary string become a session would make the workflow
messy and insecure.

**Decision:** Require session creation via `/sessions/new`, validate `session_id`
on every chat request, and expire idle sessions with TTL-based cleanup.

**Result:** Unknown sessions return 404 instead of silently creating state.

## 8. Verification lockout after repeated failures

**Status:** Accepted

**Why:** Unlimited identity attempts would make brute-force guessing too easy.

**Decision:** Lock the session after the configured number of failed identity
matches.

**Result:** Verification failures are bounded per session.

## 9. One main appointment action per user turn

**Status:** Accepted

**Why:** Supporting compound commands like `confirm the first and cancel the
second` would widen the workflow a lot for limited value in this task.

**Decision:** Keep one primary appointment action per turn for this delivery.

**Result:** The system stays easier to reason about, easier to test, and easier
to defend in review.

## 10. No deferred protected action state

**Status:** Accepted

**Why:** An earlier version tracked deferred protected actions across
verification. It worked, but it added branching and state across several files.

**Decision:** After successful verification, move the patient to
`list_appointments` instead of resuming a stored protected action automatically.

**Result:** The current flow is simpler and easier to understand, which I think
is the better trade for a take-home.
