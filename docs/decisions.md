# Design Decisions

- Use FastAPI for a simple HTTP entry point with schema validation.
- Use LangGraph `StateGraph` to keep protected-flow routing explicit.
- Use SQLite-backed LangGraph checkpoints to persist short-term thread state.
- Keep appointment mutations deterministic and patient-owned.
- Keep patient and appointment repositories in memory for the clinic demo data.
- Add a small Streamlit UI instead of a heavier frontend stack.
- Use an internal OpenAI-backed provider boundary so interpretation and phrasing can fail safely.
- Store remembered identity separately from live conversation state and make it revocable.
- Add a lightweight in-repo eval runner instead of adopting a larger evaluation framework.
