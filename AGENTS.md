# appointment-bot Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-04-15

## Active Technologies
- Python 3.11+ + FastAPI, LangGraph, Pydantic, pytest (001-build-appointment-service)
- LangGraph `InMemorySaver` for thread-scoped checkpoints; in-memory patient and appointment repositories for v1 (001-build-appointment-service)
- Python 3.11+ + FastAPI, LangGraph, Pydantic, Streamlit, OpenAI Python SDK, Langfuse Python SDK, pytest (002-frontend-llm-memory)
- LangGraph `InMemorySaver` for thread-scoped session state; in-memory patient and appointment repositories for v1 domain data (002-frontend-llm-memory)

- Python 3.11+ (document any justified deviation) + FastAPI, LangGraph, Pydantic, pytest, plus feature-specific additions (001-build-appointment-service)

## Project Structure

```text
app/
frontend/
tests/
```

## Commands

pytest

## Code Style

Python 3.11+ (document any justified deviation): Follow standard conventions

## Recent Changes
- 002-frontend-llm-memory: Added Python 3.11+ + FastAPI, LangGraph, Pydantic, Streamlit, OpenAI Python SDK, Langfuse Python SDK, pytest
- 001-build-appointment-service: Added Python 3.11+ + FastAPI, LangGraph, Pydantic, pytest

- 001-build-appointment-service: Added Python 3.11+ (document any justified deviation) + FastAPI, LangGraph, Pydantic, pytest, plus feature-specific additions

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
