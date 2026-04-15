# Architecture

This document describes the current architecture of the conversational appointment management service after the application/workflow boundary refactor.

## 1. System Overview

The system is split into a browser-facing UI, a FastAPI delivery layer, explicit application use cases and response services, a LangGraph-backed workflow adapter, and in-memory infrastructure adapters. LLM inference and optional tracing remain out-of-process dependencies.

```mermaid
flowchart LR
    subgraph clients [Clients]
        streamlit[Streamlit frontend]
    end

    subgraph interface [Interface]
        api[FastAPI routes]
    end

    subgraph application [Application]
        useCases[Use cases]
        presenters[Presenters]
        appPorts[Ports]
    end

    subgraph workflowLayer [Workflow]
        workflow[Conversation workflow]
    end

    subgraph domain [Domain]
        domainCore[Entities and domain services]
    end

    subgraph infrastructure [Infrastructure]
        repos[In-memory repositories]
        sessions[In-memory session store]
        checkpoints[LangGraph checkpointer adapter]
        llm[OpenAI provider]
    end

    streamlit --> api
    api --> useCases
    useCases --> presenters
    useCases --> appPorts
    useCases --> workflow
    workflow --> domainCore
    infrastructure -.implements.-> appPorts
    infrastructure -.implements.-> domainCore
```

## 2. Layering

The codebase follows a Clean Architecture split with explicit use cases and workflow contracts.

### Domain

`app/domain/` contains clinic concepts only:
- value objects such as `FullName`, `Phone`, and `DateOfBirth`
- entities such as `Appointment` and `Patient`
- domain services such as `VerificationService` and `AppointmentService`
- repository protocols in `app/domain/ports.py`

The domain no longer contains chatbot-specific action enums or public API result DTOs.

### Application

`app/application/` owns orchestration and boundary contracts:
- contracts in `app/application/contracts/`
- ports in `app/application/ports/`
- presenters in `app/application/presenters/`
- services in `app/application/services/`
- use cases in `app/application/use_cases/`
- session coordination in `app/application/session_service.py`

The primary use cases are:
- `CreateSessionUseCase`
- `HandleChatTurnUseCase`

The primary application services are:
- `ChatResponseService`
- `ResponsePolicy`

### Workflow

`app/graph/` remains the deterministic conversation workflow package. It interprets intent, enforces verification, executes domain actions, and produces typed workflow outcomes. Response wording is no longer a graph node responsibility.

`app/infrastructure/workflow/langgraph_runner.py` is the adapter that implements the `ConversationWorkflow` port. It is the single place that maps `ConversationWorkflowInput` into graph input and maps graph state back into `ConversationWorkflowResult`.

### Infrastructure

`app/infrastructure/` provides adapter implementations:
- `app/infrastructure/persistence/in_memory.py`
- `app/infrastructure/session/in_memory.py`
- `app/infrastructure/workflow/in_memory_checkpoint.py`
- `app/infrastructure/workflow/langgraph_runner.py`
- `app/infrastructure/llm/openai_provider.py`
- `app/infrastructure/llm/factory.py`

### Interface

`app/api/routes.py`, `app/api/schemas.py`, `app/main.py`, and the Streamlit frontend are now thin delivery adapters. They call use cases and render results rather than orchestrating workflow logic directly.

## 3. Port and Adapter Boundaries

```mermaid
flowchart TB
    subgraph domainPorts [Domain ports]
        appointmentRepo[AppointmentRepository]
        patientRepo[PatientRepository]
    end

    subgraph applicationPorts [Application ports]
        sessionStore[SessionStore]
        workflowPort[ConversationWorkflow]
        checkpointStore[CheckpointStore]
    end

    subgraph adapters [Current adapters]
        inMemAppointment[InMemoryAppointmentRepository]
        inMemPatient[InMemoryPatientRepository]
        inMemSession[InMemorySessionStore]
        inMemCheckpoint[InMemoryCheckpointStore]
        langgraphRunner[LangGraphConversationWorkflow]
        openaiProvider[OpenAIProvider]
    end

    inMemAppointment -.-> appointmentRepo
    inMemPatient -.-> patientRepo
    inMemSession -.-> sessionStore
    inMemCheckpoint -.-> checkpointStore
    langgraphRunner -.-> workflowPort
```

The important architectural change is that `app/runtime.py` is now the only composition root. The workflow builder no longer creates default repositories, providers, settings, or tracers.

## 4. Request Lifecycle

### POST /sessions/new

```mermaid
sequenceDiagram
    participant client as Client
    participant api as FastAPI
    participant uc as CreateSessionUseCase
    participant sessionSvc as SessionService

    client->>api: POST /sessions/new
    api->>uc: execute()
    uc->>sessionSvc: cleanup_expired()
    uc->>sessionSvc: create_session()
    api-->>client: NewSessionResponse
```

`CreateSessionUseCase` creates the session record and returns the initial greeting payload for the chat UI.

### POST /chat

```mermaid
sequenceDiagram
    participant client as Client
    participant api as FastAPI
    participant uc as HandleChatTurnUseCase
    participant sessionSvc as SessionService
    participant workflow as ConversationWorkflow
    participant responseSvc as ChatResponseService
    participant presenter as ChatPresenter

    client->>api: POST /chat
    api->>uc: execute(session_id, message)
    uc->>sessionSvc: cleanup_expired()
    uc->>sessionSvc: require_session(session_id)
    uc->>workflow: run(ConversationWorkflowInput)
    uc->>responseSvc: generate(workflow_result)
    uc->>presenter: present(response_text, workflow_result)
    api-->>client: ChatResponse
```

`HandleChatTurnUseCase` owns the application flow: session validation, workflow execution, response generation, and presentation.

## 5. Runtime Lifecycle

`create_runtime()` in `app/runtime.py`:
- loads `Settings`
- builds the logger and optional Langfuse tracer
- delegates repository construction to `app/runtime_assembly/repositories.py`
- delegates provider and service construction to `app/runtime_assembly/services.py`
- delegates workflow assembly to `app/runtime_assembly/workflow.py`
- delegates presenter construction to `app/runtime_assembly/presenters.py`
- delegates use case wiring to `app/runtime_assembly/use_cases.py`

`RuntimeContext` now holds the use cases as first-class dependencies:
- `create_session_use_case`
- `handle_chat_turn_use_case`

`app/main.py` still registers a lifespan that creates the runtime on startup and closes it on shutdown. `app/api/routes.py` reads `request.app.state.runtime` and lazily creates one only if needed.

## 6. Session and Workflow State

Session records are now stored through `SessionStore`, currently backed by `InMemorySessionStore`.

LangGraph checkpoint persistence is behind `CheckpointStore`, currently backed by `InMemoryCheckpointStore`.

Cross-session remembered identity was intentionally removed from the delivered product. If it is revisited later, it should return as a separate scope expansion rather than hidden session bootstrap state.

## 7. File-to-Layer Mapping

| Layer | Files |
|---|---|
| Domain | `app/domain/models.py`, `app/domain/services.py`, `app/domain/ports.py`, `app/domain/errors.py` |
| Application | `app/application/contracts/*`, `app/application/ports/*`, `app/application/presenters/*`, `app/application/services/*`, `app/application/use_cases/*`, `app/application/session_service.py` |
| Workflow | `app/graph/builder.py`, `app/graph/routing.py`, `app/graph/state.py`, `app/graph/text_extraction.py`, `app/graph/nodes/*` |
| Infrastructure | `app/infrastructure/persistence/*`, `app/infrastructure/session/*`, `app/infrastructure/workflow/*`, `app/infrastructure/llm/*`, `app/observability.py` |
| Interface | `app/main.py`, `app/api/routes.py`, `app/api/schemas.py`, `frontend/streamlit_app.py`, `frontend/lib/api_client.py` |
| Cross-cutting | `app/config.py`, `app/runtime.py`, `app/runtime_assembly/*`, `app/prompts/*`, `app/evals/*` |
