# System Design

The system now has two user-facing surfaces:

- a FastAPI backend that owns workflow state, policy gates, session bootstrap, and remembered-identity lifecycle
- a Streamlit frontend that starts sessions, renders chat history, and calls the backend over HTTP

Core design choices:

- thread-scoped LangGraph state persisted in SQLite checkpoints
- remembered identity stored separately in SQLite with explicit revoke and expiry behavior
- an internal provider boundary for interpretation, patient-facing phrasing, and eval judging
- deterministic authorization and appointment mutation logic kept outside prompts
- workflow and provider events emitted through the observability layer with redacted payloads
- tests at unit, graph, API, and eval-runner levels
