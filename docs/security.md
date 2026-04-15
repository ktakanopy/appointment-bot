# Security patterns

This document describes security-related behavior in the healthcare appointment bot.

## 1. Verification gating

**Protected operations** (`ConversationOperation.requires_verification` in `app/models.py`): `list_appointments`, `confirm_appointment`, `cancel_appointment`.

**Verification-first operations** (`ConversationOperation.triggers_verification_flow` in `app/models.py`): `help`, `unknown`, `verify_identity`.

**Verification gate** (`verification_required` in `app/graph/routing.py`): after interpretation, the workflow routes into `verify` whenever the interpreted operation is protected, is verification-first, or already has a `deferred_operation`.

**Deferred operation**: when a protected operation is requested while the user is unverified, `deferred_operation` is stored. After successful verification, `requested_operation` is restored from `deferred_operation` so the patient does not need to repeat the original request.

**Verification order**: fields are collected in sequence: full name, then phone, then date of birth.

**Matching**: verification uses normalized comparison: case-insensitive name, digits-only phone, ISO date.

**Failure handling**: when a field format is invalid, the workflow returns a typed `issue` and a deterministic response key for that field without consuming a verification attempt. When all three fields are syntactically valid but do not match a patient record, the flow clears the collected identity fields, increments the verification failure counter, and restarts from full name.

## 2. Session validation

`/sessions/new` creates a `SessionRecord` in `InMemorySessionStore`.

`/chat` uses `SessionService.require_session`, which returns HTTP 404 if `session_id` is not in the registry.

Sessions use a TTL (`SESSION_TTL_MINUTES`, default 60 minutes). Expired sessions are removed during request handling.

`last_seen_at` is updated on each chat request so active sessions remain valid while in use.

## 3. Verification lockout

`ConversationState` carries a `verification_failures` counter, incremented on each failed identity match.

`max_verification_attempts` defaults to 3 and is configurable via `MAX_VERIFICATION_ATTEMPTS`.

When failures reach the limit, `verification_status` becomes `locked` and remains locked for that session.

Locked sessions respond with a patient-facing lock message and `issue=verification_locked`.

The patient must obtain a new session via `/sessions/new` to attempt verification again.

## 4. PII redaction

From `app/observability.py`, `redact_trace_payload` runs on workflow event payloads before logging or sending traces to Langfuse.

Structured fields are redacted as follows: `provided_full_name` and `display_name` become `[redacted-name]`; `provided_phone` and `phone` become `[redacted-phone-XXXX]`; `provided_dob` and `dob` become `[redacted-dob]`.

For `messages`, each message body is processed with `_redact_message`, which masks dates and sequences of ten or more digits.

Nested dictionaries are redacted recursively.

The same redaction applies to structured log output and Langfuse trace events.

## 5. Appointment ownership

`Appointment.is_owned_by()` in `app/models.py` requires `appointment.patient_id == patient_id`.

`AppointmentService` in `app/services.py` and the appointment node handlers in `app/graph/nodes.py` enforce this before confirm or cancel operations.

If ownership does not hold, the workflow returns `issue=appointment_not_owned`.

## 6. Scope limitations

This project is a demo or exercise. The following are intentionally out of scope:

- Real authentication (OAuth, JWT, API keys)
- Encryption at rest for persisted session or identity data
- HTTPS/TLS termination at the application
- Role-based access control or multi-tenant isolation
- Audit logging beyond structured events
- Input sanitization beyond Pydantic models with `extra="forbid"`
- Cross-session remembered identity restore; this was intentionally deferred to keep the delivered scope closer to the original exercise
