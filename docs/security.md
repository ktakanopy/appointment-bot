# Security patterns

This document describes security-related behavior in the healthcare appointment bot.

## 1. Verification gating

**Protected actions** (`PROTECTED_ACTIONS` in `app/domain/policies.py`): `list_appointments`, `confirm_appointment`, `cancel_appointment`.

**Verification-first actions** (`VERIFICATION_FIRST_ACTIONS` in `app/graph/routing.py`): `help`, `unknown`, `verify_identity`.

**Verification gate** (`verification_required` in `app/graph/routing.py`): every turn passes through `verify`, which checks whether the interpreted action is protected, is verification-first, or already has a `deferred_action`. When none of those conditions apply for an unverified user, verification becomes a no-op for that turn.

**Deferred action**: when a protected action is requested while the user is unverified, `deferred_action` is stored. After successful verification, `requested_action` is restored from `deferred_action` so the patient does not need to repeat the original request.

**Verification order**: fields are collected in sequence: full name, then phone, then date of birth. Each turn collects the next missing field.

**Matching**: verification uses normalized comparison: case-insensitive name, digits-only phone, ISO date.

**Failure handling**: when a field format is invalid, the response explains which field is invalid and asks for that same field again without consuming a verification attempt. When all three fields are syntactically valid but do not match a patient record, the flow clears the collected identity fields, increments the verification failure counter, and restarts from full name with a mismatch explanation.

## 2. Session validation

`/sessions/new` creates a `SessionRecord` in `runtime.sessions` with a UUID `session_id`.

`/chat` calls `_require_session`, which returns HTTP 404 if `session_id` is not in the registry.

Sessions use a TTL (`SESSION_TTL_MINUTES`, default 60 minutes). Expired sessions are removed during request handling.

`last_seen_at` is updated on each chat request so active sessions remain valid while in use.

## 3. Verification lockout

`ConversationState` carries a `verification_failures` counter, incremented on each failed identity match.

`max_verification_attempts` defaults to 3 and is configurable via `MAX_VERIFICATION_ATTEMPTS`.

When failures reach the limit, `verification_status` becomes `locked` on the session state and is not cleared for that session.

Locked sessions respond with a message that the session is locked for security and `error_code=verification_locked`.

The patient must obtain a new session via `/sessions/new` to attempt verification again.

## 4. PII redaction

From `app/observability.py`, `redact_trace_payload` runs on workflow event payloads before logging or sending traces to Langfuse.

Structured fields are redacted as follows: `provided_full_name` and `display_name` become `[redacted-name]`; `provided_phone` and `phone` become `[redacted-phone-XXXX]` using the last four digits; `provided_dob` and `dob` become `[redacted-dob]`.

For `messages`, each message body is processed with `_redact_message`, which masks dates (formats such as YYYY-MM-DD and DD/MM/YYYY) and sequences of ten or more digits.

Nested dictionaries are redacted recursively.

The same redaction applies to structured log output and Langfuse trace events.

## 5. Remembered identity lifecycle

After successful verification, `_ensure_remembered_identity` in `app/api/routes.py` may create a `RememberedIdentity` record with:

- A SHA-256 fingerprint over normalized name, phone, date of birth, and `patient_id`
- TTL from `REMEMBERED_IDENTITY_TTL_HOURS` (default 24 hours)
- Storage in a dedicated SQLite database at `IDENTITY_DATABASE_PATH`

On `POST /sessions/new` with `remembered_identity_id`, identity is restored only if the record is active (not expired and not revoked).

`POST /remembered-identity/forget` revokes the remembered identity so it cannot be used for future restores.

Expired records are handled on read: `RememberedIdentityService._is_active` performs a lazy expiry check when determining whether an identity is active.

## 6. Appointment ownership

`appointment_is_owned_by_patient` in `app/domain/policies.py` requires `appointment.patient_id == patient_id`.

`_resolve_target_appointment` in `app/graph/nodes/appointments.py` enforces this before confirm or cancel operations.

If ownership does not hold, the response uses `error_code=appointment_not_owned`.

## 7. Scope limitations

This project is a demo or exercise. The following are intentionally out of scope:

- Real authentication (OAuth, JWT, API keys)
- Encryption at rest for SQLite databases
- HTTPS/TLS termination at the application
- Role-based access control or multi-tenant isolation
- Audit logging beyond structured events
- Input sanitization beyond Pydantic models with `extra="forbid"`
