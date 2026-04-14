# appointment-bot Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-04-13

## Active Technologies
- Python 3.11+ + FastAPI, LangGraph, Pydantic, pytes (001-build-appointment-service)
- LangGraph `InMemorySaver` for thread-scoped checkpoints; in-memory patient and appointment repositories for v1 (001-build-appointment-service)
- Python 3.11+ + FastAPI, LangGraph, Pydantic, Streamlit, OpenAI Python SDK, Langfuse Python SDK, pytes (002-frontend-llm-memory)
- SQLite-backed LangGraph checkpointer for thread-scoped session state; SQLite remembered-identity repository for bounded cross-session identity restore; in-memory patient and appointment repositories remain acceptable for v1 domain data (002-frontend-llm-memory)

- Python 3.11+ (document any justified deviation) + FastAPI, LangGraph, Pydantic, pytest, plus feature-specific additions (001-build-appointment-service)

## Project Structure

```text
backend/
frontend/
tests/
```

## Commands

cd src && pytest && ruff check .

## Code Style

Python 3.11+ (document any justified deviation): Follow standard conventions

## Recent Changes
- 002-frontend-llm-memory: Added Python 3.11+ + FastAPI, LangGraph, Pydantic, Streamlit, OpenAI Python SDK, Langfuse Python SDK, pytes
- 001-build-appointment-service: Added Python 3.11+ + FastAPI, LangGraph, Pydantic, pytes

- 001-build-appointment-service: Added Python 3.11+ (document any justified deviation) + FastAPI, LangGraph, Pydantic, pytest, plus feature-specific additions

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
