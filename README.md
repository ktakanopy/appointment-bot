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
- pytest

Key design decisions:

- a single `POST /chat` endpoint
- explicit workflow orchestration with `LangGraph StateGraph`
- short-term conversation memory keyed by `thread_id`
- deterministic safety gates for verification and protected actions
- in-memory repositories so the exercise stays focused on orchestration and
  business logic

Main structure:

```text
app/
  api/
  graph/
  domain/
  repositories/
  prompts/
tests/
  api/
  graph/
  unit/
docs/
specs/001-appointment-management/
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

## Running the Service

Start the API locally with:

```bash
uv run uvicorn app.main:app --reload
```

Then open:

- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`

## Example Usage

First message:

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

## Sample Data

The project uses in-memory repositories defined in
`app/repositories/in_memory.py`.

Valid manual test example:

- Name: `Ana Silva`
- Phone: `11999998888`
- Date of birth: `1990-05-10`

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
```

## Design Artifacts

Supporting documentation:

- `docs/sdd.md`
- `docs/decisions.md`
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
- Data is volatile and lives only in memory.
