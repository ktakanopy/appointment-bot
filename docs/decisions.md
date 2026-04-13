# Design Decisions

- Use FastAPI for a simple HTTP entry point with schema validation.
- Use LangGraph `StateGraph` to keep protected-flow routing explicit.
- Use `InMemorySaver` to persist short-term thread state during a conversation.
- Keep appointment mutations deterministic and patient-owned.
- Start with in-memory repositories so the exercise stays focused on workflow
  correctness instead of infrastructure.
