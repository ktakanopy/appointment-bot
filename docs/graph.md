# Workflow graph

This is the core of the project.

If someone asks me what the interesting part of the take-home is, I would point
here first. The graph is where the system keeps its promises: verify first,
protect patient data, and keep the flow predictable across turns.

## Why use a graph at all?

This problem looks conversational, but it is mostly a policy flow.

The system has to answer questions like:

- is the patient verified yet?
- which identity field is still missing?
- should this turn prompt for more identity data or run a business action?
- can this appointment be confirmed or canceled?

Those are workflow questions, not creative-writing questions. A LangGraph
`StateGraph` fits that pretty naturally.

## Graph shape

```mermaid
flowchart TD
    start([Start]) --> ingest[ingest]
    ingest --> interpret[interpret]
    interpret --> need_verify{verification_required?}
    need_verify -->|yes| verify[verify]
    need_verify -->|no| execute[execute_action]
    verify --> ready{turn output present?}
    ready -->|yes| finish([End])
    ready -->|no| execute
    execute --> finish
```

Each user message makes one pass through this graph.

## State shape

The graph carries one conversation state object across turns. The main top-level
fields are:

- `thread_id`
- `messages`
- `verification`
- `turn`
- `appointments`

This is the same shape you see in `workflow.end` logs and Langfuse trace
payloads.

### `thread_id`

The LangGraph conversation id.

- every turn in the same chat reuses this value
- it is the key used to resume workflow state across turns
- in traces it is also a good proxy for a conversation-level trace id

### `messages`

Serialized message history carried by the workflow.

Each item has:

- `role`: `user`, `assistant`, `system`, or `tool`
- `content`: the message text

This history is used for:

- the visible conversation transcript
- LLM interpretation context
- debugging and tracing

### `verification`

Identity-verification progress for the current session.

Fields:

- `verified`
  - `true` when the patient has been matched successfully
  - `false` otherwise
- `verification_failures`
  - count of failed full identity checks in this session
  - used to enforce lockout after repeated mismatches
- `verification_status`
  - current verification phase
  - values: `unverified`, `collecting`, `failed`, `verified`, `locked`
- `patient_id`
  - internal patient id once verification succeeds
  - `null` before that
- `provided_full_name`
  - normalized name collected so far
- `provided_phone`
  - normalized phone collected so far
- `provided_dob`
  - normalized date of birth collected so far

Why both `verified` and `verification_status` exist:

- `verified` is a simple gate for protected actions
- `verification_status` keeps the richer workflow phase

For example, both `unverified` and `collecting` imply `verified=false`, but they
mean different things for the next prompt.

### `turn`

The current-turn outcome. This is reset at the start of each user message and
then filled by the graph nodes.

Fields:

- `requested_operation`
  - the action the workflow believes it is handling now
  - values come from `ConversationOperation`
  - examples: `verify_identity`, `list_appointments`, `confirm_appointment`
- `operation_result`
  - structured result of a completed business action
  - values come from `ConversationOperationResult`
  - examples include outcomes like `listed`, `confirmed`, `already_confirmed`, `canceled`
  - this is what later becomes `last_action_result` in `ChatTurnResponse`
- `response_key`
  - deterministic key used to build the user-facing response text
  - values come from `ResponseKey`
  - examples: `collect_full_name`, `appointments_list`, `confirm_ambiguous_reference`
- `issue`
  - machine-readable description of the problem encountered in the turn
  - values come from `TurnIssue`
  - examples: `invalid_identity`, `missing_list_context`, `ambiguous_appointment_reference`
- `subject_appointment`
  - the resolved appointment for confirm/cancel when one was identified successfully
  - `null` when the turn does not target a specific appointment

Why `response_key` and `issue` are both present:

- `issue` captures what went wrong semantically
- `response_key` captures which exact response variant should be shown

That distinction matters because the same issue can map to different response
text depending on the operation. For example:

- `issue=ambiguous_appointment_reference`
- `response_key=confirm_ambiguous_reference`
- `response_key=cancel_ambiguous_reference`

### `appointments`

Appointment-selection context for the conversation.

Fields:

- `listed_appointments`
  - the last appointment list shown to the user
  - used to resolve ordinal references like `the first one`
- `appointment_reference`
  - the raw reference extracted from the latest user turn
  - examples: `1`, `2026-04-20`, `a1`
  - `null` when the user did not specify a target appointment

This split lets the workflow resolve references deterministically:

- `appointment_reference` says what the user pointed at
- `listed_appointments` says what candidate list that reference should apply to

## State example

If a user says `hi` in a fresh session, a typical end state looks like this in
plain English:

- `verification.verified = false`
- `verification.verification_status = collecting`
- no identity fields have been collected yet
- `turn.requested_operation = verify_identity`
- `turn.response_key = collect_full_name`
- `turn.issue = null`

That means the workflow interpreted the turn as the start of identity
collection, and the next assistant response should ask for the full name.

## Nodes

### `ingest`

Resets turn-level output fields so one turn does not leak into the next.

Without this step, old `response_key`, `issue`, or `operation_result` values
could stick around and produce stale responses.

### `interpret`

The only node that calls the LLM.

It extracts:

- `requested_operation`
- `full_name`
- `phone`
- `dob`
- `appointment_reference`

After that, the workflow is deterministic again.

If the provider fails here, the node raises `DependencyUnavailableError` and the
API returns HTTP 503.

### `verify`

This node owns the identity flow.

It:

- asks for missing fields one at a time
- validates field formats
- attempts the identity match when all three fields are present
- increments the failure counter on identity mismatch
- locks the session after the configured maximum number of failures

Once verification succeeds, the workflow sets the next operation to
`list_appointments` and continues.

### `execute_action`

Runs the business action once verification is no longer blocking the turn.

Depending on state, that may lead to:

- list appointments
- confirm an appointment
- cancel an appointment
- return help text

## Routing rules

After `interpret`, the graph asks one simple question: does this turn require
verification and is the patient still unverified?

- If yes, go to `verify`
- If no, go to `execute_action`

Protected operations are:

- `list_appointments`
- `confirm_appointment`
- `cancel_appointment`

The workflow also routes `help`, `unknown`, and `verify_identity` through
`verify` when the user is still in the middle of identity collection. That
sounds a little odd at first, but it works well in practice because users often
mix natural conversation with identity answers.

After `verify`, the graph checks whether the node already produced a turn
result.

- If yes, stop the turn there
- If no, continue to `execute_action`

That is why the system can ask for a missing phone number without also trying to
list appointments in the same turn.

## Example flow

### Listing before verification

1. User: `show my appointments`
2. `interpret` classifies `list_appointments`
3. `verify` asks for `full_name`
4. User provides name
5. `verify` asks for `phone`
6. User provides phone
7. `verify` asks for `dob`
8. User provides DOB
9. verification succeeds
10. `execute_action` lists appointments

### Confirm after listing

1. User: `confirm the first one`
2. `interpret` extracts `confirm_appointment` and `appointment_reference=1`
3. user is already verified, so the graph skips `verify`
4. `execute_action` resolves `1` against the stored appointment list
5. appointment is confirmed or returns an idempotent outcome if it was already confirmed

## What the graph does not do

- it does not build final HTTP responses
- it does not let the LLM decide policy
- it does not implement real authentication
- it does not replace the service layer

That boundary is deliberate. The graph owns workflow. The rest stays outside it.
