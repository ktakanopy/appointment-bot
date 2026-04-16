# Observability and Tracing

## 1. Structured Logging

The application uses the `appointment_bot` logger from `get_logger()` in `app/observability.py`.

Log lines are JSON objects written to stdout. The formatter is message-only; the logger does not add a timestamp prefix.

The default log level is INFO.

`log_event(logger, node, state, **extra)` emits one JSON object per graph node execution. Standard fields are: `thread_id`, `node`, `requested_operation`, `verified`, `verification_status`, `issue`, plus any node-specific extras (for example `appointment_count`, `outcome`, and `appointment_id`).

## 2. Trace Event Catalog

Events emitted through `record_trace_event` and `record_provider_event`:

| Event | Emitter | Payload |
|-------|---------|---------|
| workflow.start | `LangGraphWorkflow.run()` | thread_id, full workflow payload (redacted) |
| workflow.end | `LangGraphWorkflow.run()` | thread_id, full workflow result (redacted) |
| provider.interpret | OpenAIProvider.interpret | provider name, status |
| provider.judge | OpenAIProvider.judge | provider name, status |

Per-node log events (via `log_event`, not `record_trace_event`):

- ingest_user_message
- parse_intent_and_entities (plus `appointment_reference`)
- collect_missing_verification_fields
- verify_identity (plus `outcome`: verified, failed, or locked)
- execute_action (plus `outcome=skipped` when verification already produced the turn response)
- list_appointments (plus `appointment_count`)
- confirm_appointment (plus `outcome`, `appointment_id`)
- cancel_appointment (plus `outcome`, `appointment_id`)
- resolve_appointment_reference (plus `outcome`: ambiguous or missing_list_context)
- handle_help_or_unknown

## 3. Langfuse Integration

The tracer is built with `build_tracer(settings)` in `app/observability.py`.

Tracing requires `TRACING_ENABLED=true` and valid `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY`.

The integration uses the Langfuse client with `create_event(name=..., body=...)` for each trace event.

Import and constructor failures are caught; the builder returns `None` so tracing is optional.

## 4. PII Redaction Pipeline

All trace payloads pass through `redact_trace_payload` before they reach the logger or Langfuse.

| Field pattern | Redacted to |
|---------------|-------------|
| provided_full_name, display_name | [redacted-name] |
| provided_phone, phone | [redacted-phone-XXXX] (last 4 digits preserved) |
| provided_dob, dob | [redacted-dob] |
| messages[].content | Regex replaces YYYY-MM-DD, DD/MM/YYYY dates and 10+ digit numbers |
| Nested dicts | Recursively redacted |

See `docs/security.md` for the full security context.

## 5. Failure Isolation

Tracing failures should not interrupt the request path.

`record_trace_event` wraps `tracer.create_event` in try/except. On failure, a line is logged with `{"event": ..., "trace_status": "unavailable"}`.

Tests cover this: `test_chat_flow_succeeds_when_tracing_backend_fails` uses a BrokenTracer that raises on every call.

## 6. Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| TRACING_ENABLED | auto (true if keys present) | Enable Langfuse tracing |
| LANGFUSE_PUBLIC_KEY | (none) | Langfuse public key |
| LANGFUSE_SECRET_KEY | (none) | Langfuse secret key |
| LANGFUSE_HOST | https://cloud.langfuse.com | Langfuse host URL |
| LOG_LEVEL | INFO | Application log level |
