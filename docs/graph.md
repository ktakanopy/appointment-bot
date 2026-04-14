# Workflow Graph

```mermaid
flowchart TD
    start([Start]) --> ingest[ingest_user_message]
    ingest --> interpret[parse_intent_and_entities]

    interpret -->|not verified and protected action| verify[verification_subgraph]
    interpret -->|not verified and help unknown or verify_identity| verify
    interpret -->|not verified and deferred_action exists| verify
    interpret -->|list_appointments| list[list_appointments]
    interpret -->|confirm_appointment| confirm[confirm_appointment]
    interpret -->|cancel_appointment| cancel[cancel_appointment]
    interpret -->|fallback| help[handle_help_or_unknown]

    verify -->|response_text and still not verified| respond[generate_response]
    verify -->|list_appointments| list
    verify -->|confirm_appointment| confirm
    verify -->|cancel_appointment| cancel
    verify -->|fallback| help

    list --> respond
    confirm --> respond
    cancel --> respond
    help --> respond
    respond --> finish([End])
```

## Notes

- The graph is compiled in `app/graph/builder.py` with `InMemorySaver`.
- `route_after_interpret()` sends the flow to `verification_subgraph` whenever the patient is not verified and the action is protected, is an early verification-style action, or a deferred action already exists.
- `route_after_verification()` goes straight to `generate_response` when verification still needs more data or the session is locked and a response is already prepared.
- Once verification succeeds, the graph resumes the intended action path without requiring the user to restate it.
- `generate_response` always stays after deterministic business logic so the LLM never controls authorization or state mutation.
