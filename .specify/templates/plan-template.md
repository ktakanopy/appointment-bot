# Implementation Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link]
**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

[Extract from feature spec: primary requirement + technical approach from research]

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: Python 3.11+ (document any justified deviation)  
**Primary Dependencies**: FastAPI, LangGraph, Pydantic, pytest, plus feature-specific additions  
**Storage**: Thread-scoped checkpointer for conversation state; repository-backed domain data (in-memory in v1 unless justified otherwise)  
**Testing**: pytest for unit, graph, and API coverage  
**Target Platform**: Linux server or containerized API runtime
**Project Type**: Conversational backend web-service  
**Performance Goals**: Preserve safe conversational correctness first; document any explicit latency or throughput targets introduced by the feature  
**Constraints**: Deterministic authorization, minimal PII in logs, idempotent protected mutations, graceful fallback on LLM and repository failures  
**Scale/Scope**: Single-clinic prototype unless the feature spec explicitly expands scope

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [ ] Protected actions are enumerated and gated in deterministic backend code.
- [ ] Conversation state, `session_id` to `thread_id` mapping, deferred intent, and rerouting behavior are explicit.
- [ ] The LLM boundary is documented, including deterministic fallback when parsing is ambiguous.
- [ ] Unit, graph, and API tests cover verification, ownership, idempotency, and failure recovery.
- [ ] Structured logs or traces are defined with privacy-aware handling of patient data.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```text
app/
├── main.py
├── api/
│   ├── routes.py
│   └── schemas.py
├── graph/
│   ├── builder.py
│   ├── routing.py
│   ├── state.py
│   ├── nodes/
│   └── subgraphs/
├── domain/
├── repositories/
└── prompts/

tests/
├── api/
├── graph/
└── unit/

docs/
```

**Structure Decision**: Default to the single FastAPI + LangGraph backend
layout above. Any deviation must be justified in the plan.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
