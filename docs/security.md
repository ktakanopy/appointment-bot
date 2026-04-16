# Security patterns

This is still a demo project, but the workflow does enforce a few real safety
rules.

## Verification gating

Protected operations are:

- `list_appointments`
- `confirm_appointment`
- `cancel_appointment`

If the patient is not verified, the workflow routes into `verify` before any of
those actions can run.

The verification flow collects fields in order:

1. full name
2. phone
3. date of birth

Field-format problems do not consume a verification attempt. Identity mismatches
do.

## Session validation

The app does not accept arbitrary `session_id` values.

- `/sessions/new` creates a `SessionRecord`
- `/chat` requires that session to exist
- unknown sessions return HTTP 404

Sessions also expire after a TTL. Expired sessions are cleaned up during request
handling.

## Verification lockout

Each failed identity match increments a counter.

When the counter reaches `MAX_VERIFICATION_ATTEMPTS` (default `3`), the session
is locked and the workflow returns `issue=verification_locked`.

At that point the patient has to start a new session.

## Appointment ownership

Confirm and cancel operations check appointment ownership before mutation.

That happens through `Appointment.is_owned_by()` and service-level checks in
`AppointmentService`.

If the appointment does not belong to the verified patient, the workflow returns
an ownership-related issue instead of mutating data.

## PII redaction

Logs and trace payloads are redacted before they leave the workflow layer.

- names are masked
- phones are masked except for the last four digits
- DOB values are masked
- message contents have dates and long digit sequences scrubbed

## What this project does not try to be

This is not a full security implementation.

Out of scope:

- real auth such as OAuth or JWT
- encryption at rest
- TLS termination
- RBAC or multi-tenant isolation
- full audit trails
- cross-session remembered identity

That said, the app does enforce the security properties that matter most for the
exercise itself: verification before access, bounded retry attempts, ownership
checks, and redaction in logs and traces.
