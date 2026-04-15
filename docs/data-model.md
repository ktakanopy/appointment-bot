# Data model

## 1. Entity Relationships

```mermaid
erDiagram
    Patient ||--o{ Appointment : has
    Patient ||--o{ RememberedIdentity : has
    Patient {
        string id PK
        string full_name
        string phone
        date date_of_birth
    }
    Appointment {
        string id PK
        string patient_id FK
        date date
        string time
        string doctor
        string status
    }
    RememberedIdentity {
        string remembered_identity_id PK
        string patient_id FK
        string display_name
        string verification_fingerprint
        datetime issued_at
        datetime expires_at
        datetime revoked_at
        string status
    }
    ConversationOperationResult {
        string operation
        string outcome
        string appointment_id
    }
```

`ConversationOperationResult` is an application/workflow contract used to describe the outcome of a completed operation; it is not persisted.

## 2. AppointmentStatus State Machine

```mermaid
stateDiagram-v2
    [*] --> scheduled
    scheduled --> confirmed : confirm_appointment
    scheduled --> canceled : cancel_appointment
    confirmed --> confirmed : confirm_appointment\n(idempotent: already_confirmed)
    confirmed --> canceled : cancel_appointment
    canceled --> canceled : cancel_appointment\n(idempotent: already_canceled)
```

Confirming a `scheduled` appointment transitions to `confirmed`. Re-confirming an already `confirmed` appointment returns outcome `already_confirmed` without error. Canceling transitions `scheduled` or `confirmed` to `canceled`. Re-canceling an already `canceled` appointment returns outcome `already_canceled` without error. A `canceled` appointment cannot be confirmed.

## 3. RememberedIdentityStatus Lifecycle

```mermaid
stateDiagram-v2
    [*] --> unavailable
    unavailable --> active : identity issued
    active --> expired : expires_at before now\n(lazy on access)
    active --> revoked : POST /remembered-identity/forget
```

`unavailable` is the initial state when no remembered identity exists for the session.

## 4. ConversationState Reference

| Field | Type | Purpose |
|-------|------|---------|
| thread_id | str | Unique conversation thread identifier, same as session_id |
| incoming_message | str | Current user message being processed |
| messages | list[dict] | Full conversation history (role + content pairs) |
| verified | bool | Whether identity verification has succeeded |
| verification_failures | int | Count of failed verification attempts in this session |
| verification_status | `VerificationStatus` | Current phase: unverified, collecting, failed, verified, or locked |
| patient_id | str or None | Matched patient ID after successful verification |
| provided_full_name | str or None | Name provided by the patient during verification |
| provided_phone | str or None | Phone provided by the patient during verification |
| provided_dob | str or None | Date of birth provided by the patient during verification |
| requested_operation | `ConversationOperation` | Current operation being processed |
| deferred_operation | `ConversationOperation` or None | Protected operation deferred until verification completes |
| listed_appointments | list[Appointment] | Appointments returned by the last list action |
| appointment_reference | str or None | User's reference to a specific appointment (ordinal, date, id) |
| operation_result | `ConversationOperationResult` or None | Outcome of the last completed operation |
| response_key | `ResponseKey` or None | Deterministic presenter key for the patient-facing response |
| issue | `TurnIssue` or None | Machine-readable issue classification for the current turn |

## 5. Persistence Strategy

| Data | Storage | Lifetime |
|------|---------|----------|
| Patient records | In-memory (InMemoryPatientRepository) | Process lifetime |
| Appointment records | In-memory (InMemoryAppointmentRepository) | Process lifetime |
| Conversation state (per-thread) | In-memory via LangGraph InMemorySaver | Process lifetime |
| Remembered identity | In-memory (InMemoryRememberedIdentityRepository) | Process lifetime, TTL + revoke |
| Session registry | In-memory via `InMemorySessionStore` | Process lifetime, TTL-based cleanup |
| Session bootstrap | In-memory on each `SessionRecord` via `SessionBootstrap` | 300s TTL |

In-memory storage is intentional for demo scope. A production system would back conversation state, remembered identity, patient data, and appointment data with external persistence.
