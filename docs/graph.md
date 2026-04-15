# Workflow Graph

```mermaid
flowchart TD
    start([Start]) --> ingest[ingest]
    ingest --> interpret[interpret]
    interpret --> need_verify{verification_required?}
    need_verify -->|yes| verify[verify]
    need_verify -->|no| execute[execute_action]
    verify --> readyForAction{turn output present?}
    readyForAction -->|yes| finish([End])
    readyForAction -->|no| execute
    execute --> finish
```

## Notes

- The graph is compiled in `app/graph/builder.py` with an injected `InMemorySaver` checkpointer from the runtime.
- `interpret` extracts the structured operation and entity fields, filling identity inputs when they can be safely normalized, then routes through explicit conditional edges.
- `verify` is the gatekeeper for protected and verification-first turns: it either passes through, asks for the next verification field, returns a typed issue, or locks the session after repeated failures.
- `execute_action` runs deterministic business logic for list, confirm, cancel, or help only when verification did not already finish the turn.
- Once verification succeeds, the graph resumes the intended operation path through `deferred_operation` without requiring the user to restate it.
- `ConversationState.turn` now acts as the ephemeral output for the current turn, while verification and appointment state remain persisted across turns.
- The graph now ends with `ConversationState`. Response wording and HTTP shaping are generated later by `app/responses.py` and `app/main.py`, outside the workflow.
- The conditional edges make the workflow visible in the graph itself instead of hiding all routing decisions inside node internals.
