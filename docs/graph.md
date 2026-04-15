# Workflow Graph

```mermaid
flowchart TD
    start([Start]) --> ingest[ingest_user_message]
    ingest --> interpret[parse_intent_and_entities]
    interpret --> need_verify{verification_required?}
    need_verify -->|yes| verify[verify]
    need_verify -->|no| execute[execute_action]
    verify --> ready_for_action{response already prepared?}
    ready_for_action -->|yes| respond[generate_response]
    ready_for_action -->|no| execute
    execute --> respond[generate_response]
    respond --> finish([End])
```

## Notes

- The graph is compiled in `app/graph/builder.py` with `InMemorySaver`.
- `parse_intent_and_entities` extracts the structured action and entity fields, filling identity inputs when they can be safely normalized, then routes through an explicit LangGraph conditional edge.
- `verify` is the gatekeeper for protected and verification-first turns: it either passes through, asks for the next verification field, returns a validation error, or locks the session after repeated failures.
- `execute_action` runs deterministic business logic for list, confirm, cancel, or help only when the verification step did not already finish the turn.
- Once verification succeeds, the graph resumes the intended action path through `deferred_action` without requiring the user to restate it.
- `generate_response` always stays after deterministic business logic so the LLM never controls authorization or state mutation.
- The conditional edges make the workflow visible in the graph itself instead of hiding all routing decisions inside node internals.
