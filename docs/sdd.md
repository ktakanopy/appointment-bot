# System Design

The service is a single FastAPI backend with one conversational `POST /chat`
endpoint. LangGraph `StateGraph` handles routing across verification, list,
confirm, cancel, and help paths. The design keeps the LLM boundary optional and
bounded while making authorization and mutation safety deterministic.

Core design choices:

- thread-scoped conversation state keyed by `session_id`
- reusable verification subgraph before protected actions
- repository interfaces with in-memory v1 implementations
- structured logging for decision-path visibility
- tests at unit, graph, and API levels
