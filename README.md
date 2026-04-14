# Appointment Bot

Conversational appointment management service for a clinic workflow.

The main endpoint accepts natural language messages and lets a patient:

- verify their identity with full name, phone number, and date of birth
- list their appointments
- confirm an appointment
- cancel an appointment
- move naturally between these actions within the same conversation

## How This Project Was Built

I started from the exercise statement in `task_description.pdf`.

The first step was turning that prompt into a clearer working specification
through a discussion with `gpt-5.4`, using the PDF as the source of truth for
requirements, scope, flows, and constraints.

After that, I used GitHub's [`spec-kit`](https://github.com/github/spec-kit) to
structure the work as a spec-driven workflow. That process produced and guided
the following artifacts:

- project constitution
- feature specification
- implementation plan
- research notes
- data model
- API contract
- task breakdown

The main artifacts from that process live in:

- `specs/001-appointment-management/`
- `.specify/`

## Architecture

This project is built with:

- Python 3.11+
- FastAPI
- LangGraph
- Pydantic
- Streamlit
- OpenAI Python SDK
- Langfuse Python SDK
- pytest

Key design decisions:

- a single `POST /chat` endpoint
- a `POST /sessions/new` bootstrap endpoint and a `POST /remembered-identity/forget` revoke endpoint
- explicit workflow orchestration with `LangGraph StateGraph`
- in-memory conversation state keyed by `thread_id`
- deterministic safety gates for verification and protected actions
- a lightweight Streamlit frontend for patient chat
- in-memory repositories for patients, appointments, and remembered identity

Main structure:

```text
app/
  api/
  evals/
  graph/
  domain/
  llm/
  repositories/
  prompts/
frontend/
tests/
  api/
  evals/
  graph/
  unit/
docs/
specs/001-appointment-management/
specs/002-frontend-llm-memory/
```

## Important Business Rules

- listing, confirming, and canceling appointments only work after verification
- verification requires full name, phone number, and date of birth
- deferred protected actions resume automatically after successful verification
- confirmation and cancellation are idempotent
- the system avoids exposing another patient's data

## Environment Setup

### Requirements

- Python 3.11+
- `uv`

### Install dependencies

```bash
uv sync --extra dev
```

You can also rely on `uv run` if you prefer not to manage the virtual
environment manually.

### Configure environment

Copy the values you need from `.env.example`, then export the provider and tracing settings you want to use.

Minimum provider setup:

```bash
export OPENAI_API_KEY=your_key_here
export OPENAI_MODEL=gpt-4o-mini
```

Optional tracing setup:

```bash
export TRACING_ENABLED=true
export LANGFUSE_PUBLIC_KEY=your_public_key
export LANGFUSE_SECRET_KEY=your_secret_key
export LANGFUSE_HOST=https://cloud.langfuse.com
```

When running the full Docker Compose stack, local Langfuse credentials are
bootstrapped automatically unless you override them.

## Running the Service

Start the API locally with:

```bash
uv run uvicorn app.main:app --reload
```

Then open:

- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`

Start the frontend with:

```bash
uv run streamlit run frontend/streamlit_app.py
```

Then open the Streamlit URL shown in the terminal.

## Example Usage

Create a new session:

```bash
curl -X POST http://localhost:8000/sessions/new
```

Then use the returned `session_id` for chat turns:

```bash
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"demo-session-1","message":"I want to see my appointments"}'
```

Continue the same conversation:

```bash
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"demo-session-1","message":"Ana Silva"}'

curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"demo-session-1","message":"11999998888"}'

curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"demo-session-1","message":"1990-05-10"}'
```

After the appointment list is returned, the patient can continue with:

```bash
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"demo-session-1","message":"confirm the first one"}'
```

or:

```bash
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"demo-session-1","message":"cancel the first one"}'
```

If a response includes an active `remembered_identity_status.remembered_identity_id`, you can restore it in a new session:

```bash
curl -X POST http://localhost:8000/sessions/new \
  -H 'Content-Type: application/json' \
  -d '{"remembered_identity_id":"<remembered-identity-id>"}'
```

## Sample Data

The project uses in-memory patient and appointment repositories defined in
`app/repositories/in_memory.py`.

Valid manual test identities:

- Name: `Ana Silva`
- Phone: `11999998888`
- Date of birth: `1990-05-10`
- Name: `Carlos Souza`
- Phone: `11911112222`
- Date of birth: `1985-09-22`

The bot only verifies identity when the full name, phone number, and date of
birth all match the same seeded patient record. Any other combination will
return `invalid_identity` and restart the verification flow.

## Running Tests

Full suite:

```bash
uv run --extra dev pytest
```

By layer:

```bash
uv run --extra dev pytest tests/unit
uv run --extra dev pytest tests/graph
uv run --extra dev pytest tests/api
uv run --extra dev pytest tests/evals
```

Offline evaluation:

```bash
uv run python -m app.evals.runner
```

## Design Artifacts

Architecture documentation:

- `docs/architecture.md`
- `docs/llm-boundary.md`
- `docs/security.md`
- `docs/data-model.md`
- `docs/observability.md`
- `docs/evaluation.md`
- `docs/decisions.md`
- `docs/graph.md`
- `docs/test-scenarios.md`

Specification artifacts:

- `specs/001-appointment-management/spec.md`
- `specs/001-appointment-management/plan.md`
- `specs/001-appointment-management/research.md`
- `specs/001-appointment-management/data-model.md`
- `specs/001-appointment-management/contracts/chat-api.yaml`
- `specs/001-appointment-management/tasks.md`

## Notes

- The project is intentionally scoped to the exercise and uses simplified
  identity verification.
- There is no real EHR/EMR integration.
- Appointment, session, conversation, and remembered identity data remain in memory.

## Scaling Ideas

If this application needed to move beyond demo scope, the next improvements would be:

- stream token output from the backend to the frontend instead of waiting for full responses
- replace in-memory state with an external database or cache so sessions and remembered identity survive restarts
- move patient and appointment data to a real persistence layer instead of seeded demo data
- add background workers and queueing for slower downstream operations or audits
- add stronger auth, rate limiting, and production-grade observability around protected flows



## Docker

Build and run everything with Docker Compose:

```bash
docker-compose up --build
```

If your Docker installation supports the plugin-based CLI, this works too:

```bash
docker compose up --build
```

Then open:

- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- Streamlit: `http://localhost:8501`
- Langfuse: `http://localhost:3000`

The Compose stack starts:

- `api`
- `frontend`
- `langfuse-web`
- `langfuse-worker`
- `langfuse-postgres`
- `langfuse-clickhouse`
- `langfuse-minio`
- `langfuse-redis`

Default local Langfuse bootstrap values:

- Email: `admin@appointment-bot.local`
- Password: `appointment-bot-dev`
- Public key: `lf_pk_local_dev_key`
- Secret key: `lf_sk_local_dev_key`

By default, the API container points tracing at the local Langfuse instance via
`http://langfuse-web:3000`. Override `TRACING_ENABLED`, `LANGFUSE_HOST`,
`LANGFUSE_PUBLIC_KEY`, and `LANGFUSE_SECRET_KEY` if you want to disable tracing
or send traces somewhere else.

## Additional Docs

- `docs/architecture.md` -- system overview, layered architecture, data flows
- `docs/llm-boundary.md` -- LLM provider boundary, fallback, prompt design
- `docs/security.md` -- verification gating, session validation, PII redaction
- `docs/data-model.md` -- domain models, state machine, persistence strategy
- `docs/observability.md` -- structured logging, Langfuse, trace events
- `docs/evaluation.md` -- eval framework, scenarios, judge modes
- `docs/decisions.md` -- architecture decision records
- `docs/graph.md` -- workflow graph diagram
