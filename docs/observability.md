# Observability and tracing

The app logs structured workflow events and can optionally send traces to
Langfuse.

Nothing fancy here. Just enough to understand what happened in a conversation
without drowning in noise.

## Structured logs

The main app logger is `appointment_bot` from `get_logger()` in
`app/observability.py`.

Default behavior:

- logs are JSON
- they go to stdout
- level is `INFO`

`log_event(logger, node, state, **extra)` emits one structured record per graph
node execution.

Common fields:

- `thread_id`
- `node`
- `requested_operation`
- `verified`
- `verification_status`
- `issue`

Some nodes also add fields such as `outcome`, `appointment_reference`,
`appointment_count`, or `appointment_id`.

## Workflow trace events

`record_trace_event` and `record_provider_event` emit higher-level events such
as:

- `workflow.start`
- `workflow.end`
- `provider.interpret`
- `provider.judge`

There is also a separate eval logger, `appointment_bot.eval`, that formats logs
in a more human-readable way for scenario runs.

## Redaction

All trace payloads go through `redact_trace_payload()` before they are logged or
sent to Langfuse.

Redaction rules:

- names become `[redacted-name]`
- phones become `[redacted-phone-XXXX]`
- DOB fields become `[redacted-dob]`
- message bodies have dates and long digit strings masked with regexes

Nested dictionaries are redacted recursively.

## Langfuse integration

Tracing is optional.

It is enabled only when:

- `TRACING_ENABLED=true`
- `LANGFUSE_PUBLIC_KEY` is present
- `LANGFUSE_SECRET_KEY` is present

If the client import or constructor fails, the tracer is disabled and the app
keeps running.

## Failure isolation

Tracing failures should never break the request path.

If `tracer.create_event(...)` raises, the app logs a trace-unavailable event and
continues. That behavior is covered by tests.

## Useful env vars

| Variable | Purpose | Default |
|---|---|---|
| `TRACING_ENABLED` | Toggle Langfuse tracing | auto if keys are present |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key | none |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key | none |
| `LANGFUSE_HOST` | Langfuse host | none |
