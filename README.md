# Appointment Bot

Appointment Bot is a take-home implementation of a clinic appointment assistant.
It lets a patient verify identity, list appointments, confirm an appointment,
and cancel an appointment in the same chat session.

I kept the workflow explicit on purpose. The hard part of this exercise is not
writing a chatbot that sounds clever. It is making sure verification,
appointment ownership, lockout behavior, and idempotent mutations stay
predictable.

Demo asset: [chat flow GIF](docs/demo-chat-flow.gif)

## What it does

- verifies identity with full name, phone number, and date of birth
- lists appointments after verification
- confirms appointments
- cancels appointments
- lets the user move between those actions in one conversation
- exposes the flow through a FastAPI backend and a small Streamlit frontend

## Quickstart

### Requirements

- Python 3.11+
- `uv`
- `OPENAI_API_KEY`

### Run locally

This is the fastest way to review the project.

```bash
uv sync --extra dev
export OPENAI_API_KEY=your_key_here
export OPENAI_MODEL=gpt-4o-mini
uv run uvicorn app.main:app --reload
```

Then open:

- API docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

Optional frontend:

```bash
uv run streamlit run frontend/streamlit_app.py
```

### Run with Docker Compose

If you want the full local stack, including Streamlit and Langfuse:

```bash
docker compose up --build
```

That starts:

- API: `http://localhost:8000`
- Streamlit: `http://localhost:8501`
- Langfuse: `http://localhost:3000`

## Try it quickly

The project ships with seeded demo patients in `app/repositories.py`. These are
the two valid identity sets:

- `Ana Silva` / `11999998888` / `1990-05-10`
- `Carlos Souza` / `11911112222` / `1985-09-22`

A fast happy path looks like this:

1. `show my appointments`
2. `Ana Silva`
3. `11999998888`
4. `1990-05-10`
5. `confirm the first one`

After verification, the workflow shows the appointment list. From there the
patient can continue with messages like:

- `list my appointments`
- `confirm the first one`
- `cancel the first one`

If the name, phone, and date of birth do not belong to the same patient, the
bot returns `issue=invalid_identity` and restarts verification.

## Run tests

Full suite:

```bash
uv run --extra dev pytest
```

By area:

```bash
uv run --extra dev pytest tests/unit
uv run --extra dev pytest tests/graph
uv run --extra dev pytest tests/api
uv run --extra dev pytest tests/evals
```

Offline eval runner:

```bash
uv run python -m app.evals.runner
```

The eval runner replays multi-turn scenarios through the real workflow, prints
one result block per scenario, and saves machine-readable output under
`.eval_runs/`.

## Design choices

### Deterministic workflow over a free-form agent

I used LangGraph as an explicit workflow, not as an open-ended agent loop. The
model interprets the user's message, but policy decisions stay in Python.

That matters here because the risky parts are not creative tasks. They are
things like:

- whether the patient is verified
- whether an appointment belongs to that patient
- whether confirm or cancel should be idempotent
- whether the session should be locked after repeated failed verification

Those rules are easier to test and easier to explain when they are encoded in
the graph instead of hidden inside model behavior.

### The LLM has a narrow job

The live chat path uses the LLM for intent and entity extraction only.

It can suggest:

- `requested_operation`
- `full_name`
- `phone`
- `dob`
- `appointment_reference`

It does not decide authorization, mutate appointments, or generate the final
patient-facing response. Final wording comes from deterministic response
templates in `app/responses.py`.

### Post-verification flow stays simple

After successful verification, the workflow moves the patient to
`list_appointments`.

I intentionally kept that simple. A more clever version could try to remember a
pending protected action and resume it automatically. I cut that back because it
added state and branching that did not earn its keep in a take-home exercise.

### Storage is intentionally small

- patient and appointment data are seeded in memory
- session records live in `InMemorySessionStore`
- LangGraph checkpoints persist in local SQLite via `SqliteSaver`

This gives the project enough statefulness to show the workflow clearly without
dragging in a production persistence layer.

## Project shape

The main pieces are:

- `app/main.py`: FastAPI routes
- `app/runtime.py`: runtime wiring and dependency creation
- `app/graph/`: workflow nodes, state, routing, and the LangGraph wrapper
- `app/services.py`: verification, appointment, and session services
- `app/repositories.py`: seeded in-memory repositories
- `app/responses.py`: deterministic response building
- `app/llm/`: OpenAI provider, schemas, and prompt
- `frontend/`: Streamlit chat UI
- `tests/`: unit, graph, API, and eval coverage

If you want more detail, start with:

- [`docs/architecture.md`](docs/architecture.md)
- [`docs/graph.md`](docs/graph.md)
- [`docs/llm-boundary.md`](docs/llm-boundary.md)

## Scope and trade-offs

This project is intentionally exercise-sized.

What is in scope:

- session-based chat flow
- verification-gated access to appointments
- listing, confirming, and canceling appointments
- rerouting between those actions in one session
- test coverage around the main workflow and failure paths

What is intentionally out of scope:

- real EHR or EMR integration
- real authentication beyond demo identity verification
- cross-session remembered identity
- multiple appointment mutations in one user message
- production-grade persistence for patients, appointments, and sessions

Another deliberate choice: if the LLM provider fails, the `/chat` endpoint
returns a controlled HTTP 503 instead of trying to guess the user's intent with
a fallback parser. For this exercise, I preferred a clean failure over a noisy,
half-reliable recovery path.

## Documentation

The `docs/` folder has the main technical notes:

- [`docs/architecture.md`](docs/architecture.md): system layout and request flow
- [`docs/graph.md`](docs/graph.md): workflow behavior and routing
- [`docs/llm-boundary.md`](docs/llm-boundary.md): what the model can and cannot do
- [`docs/security.md`](docs/security.md): verification, lockout, ownership, and redaction
- [`docs/data-model.md`](docs/data-model.md): entities, workflow state, and persistence
- [`docs/observability.md`](docs/observability.md): logs, tracing, and redaction
- [`docs/evaluation.md`](docs/evaluation.md): eval runner and scenarios
- [`docs/decisions.md`](docs/decisions.md): architecture decisions
- [`docs/test-scenarios.md`](docs/test-scenarios.md): manual test checklist

## Process notes

I used the exercise prompt as the source of truth and kept the planning
artifacts in:

- `specs/001-appointment-management/`
- `specs/002-frontend-llm-memory/`

I would not expect a reviewer to read those first. They are there if you want
to see the design trail.

## What I'd improve next

If I were taking this beyond demo scope, the next changes would be pretty
practical:

- stream responses to the frontend so the chat feels faster
- move sessions, checkpoints, patients, and appointments to real persistence
- add stronger auth, rate limiting, and more audit-friendly controls around protected flows
- add a small deterministic fallback for a few well-covered extraction cases when the provider is unavailable
- replace request-path cleanup and in-memory mutable state with safer background cleanup and shared storage
- expand evaluation coverage for more natural-language variation and edge cases
- add cross-session remembered identity only if the product actually needs it
