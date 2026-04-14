# Workflow Graph

```mermaid
flowchart TD
    start([Start]) --> ingest[ingest_user_message]
    ingest --> interpret[parse_intent_and_entities]

    interpret -->|unverified protected action| verify[verification_subgraph]
    interpret -->|list_appointments| list[list_appointments]
    interpret -->|confirm_appointment| confirm[confirm_appointment]
    interpret -->|cancel_appointment| cancel[cancel_appointment]
    interpret -->|help or unknown| help[handle_help_or_unknown]

    verify -->|verified + deferred list| list
    verify -->|verified + deferred confirm| confirm
    verify -->|verified + deferred cancel| cancel
    verify -->|still collecting or locked| respond[generate_response]
    verify -->|fallback| help

    list --> respond
    confirm --> respond
    cancel --> respond
    help --> respond
    respond --> end([End])
```

## Notes

- Protected actions are always re-routed through verification until identity is verified.
- Verification can resume the deferred protected action without asking the patient to repeat it.
- Response generation stays downstream from deterministic business logic so the LLM never controls authorization or state mutation.
