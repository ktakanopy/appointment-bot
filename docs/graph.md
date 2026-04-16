# Workflow Graph

This guide explains how the conversation workflow is structured, why it was designed this way, and how each part connects to the business logic. You can read it alongside the code, but it should also stand on its own.

---

## 1. Why this graph exists

Appointment management in a clinical context is mostly a stateful policy problem, not an open-ended reasoning problem.

The user must verify their identity before accessing their appointments. The system collects identity fields one at a time, validates each one, matches them against a patient record, and gates all protected operations behind that match. If the user asks for an appointment action before being verified, the system stores that intent and resumes it automatically after verification succeeds.

This does not require creative reasoning or open-ended tool selection. It needs explicit state, clear routing, and predictable behavior.

A LangGraph `StateGraph` fits this problem directly because:

- routing decisions are encoded as conditional edges, visible in the graph itself
- verification state persists across turns without relying on the LLM to remember anything
- every execution path is inspectable and testable
- a bad LLM output can affect intent classification, but it cannot override policy routing

The alternative — a ReAct-style agent — would give the model authority over when to verify, when to list, and when to stop. That is more flexibility than this problem needs, and it comes at the cost of auditability and predictability. For a healthcare-adjacent workflow, the trade-off clearly favors explicit control flow.

---

## 2. Graph overview

```mermaid
flowchart TD
    start([Start]) --> ingest[ingest]
    ingest --> interpret[interpret]
    interpret --> need_verify{verification_required?}
    need_verify -->|yes| verify[verify]
    need_verify -->|no| execute[execute_action]
    verify --> readyForAction{turn output present?}
    readyForAction -->|yes| finish([End])
    readyForAction -->|no| execute
    execute --> finish
```

Each user message triggers one full pass through this graph. The graph reads the current conversation state, runs the appropriate steps, and ends with a populated turn result. Response wording and HTTP shaping happen after the graph exits, in `app/responses.py` and `app/main.py`.

The flow for a typical turn:

1. `ingest` resets per-turn output so nothing from the previous turn leaks in.
2. `interpret` reads the message, extracts intent and identity fields, and decides whether verification is required. This is the only step that calls the LLM.
3. If verification is needed, `verify` runs next. It collects missing fields, validates them, runs the identity match, or locks the session.
4. If `verify` produced a response for this turn (e.g., "please provide your phone number"), the graph ends there.
5. If `verify` completed the identity match and there is a deferred action, the graph continues to `execute_action`.
6. If verification was not required at all, `execute_action` runs directly.

---

## 3. Node-by-node walkthrough

### ingest

**Input:** current graph state
**Changes:** clears per-turn output fields (`response_key`, `issue`, `operation_result`, `subject_appointment`)
**Why it exists:** LangGraph persists state across turns via its checkpointer. Without a reset step, the response key or issue from the previous turn would still be set when the next turn starts. `ingest` ensures every turn starts from a clean output surface.
**User-facing behavior:** invisible to the user, but prevents stale data from carrying into the current response.

---

### interpret

**Input:** the latest user message and the last few turns of conversation history
**Changes:** sets `requested_operation`, fills any identity fields the user provided, decides whether to route to `verify` or `execute_action`
**Why it exists:** the system needs to understand what the user wants before it can do anything. This is the one step where the LLM is involved.
**User-facing behavior:** correctly classifies messages like "show me my appointments", "confirm the first one", "Ana Silva", or "1990-05-10" into structured operations and identity fields.

The LLM is used here for intent classification and entity extraction. After this node, control returns entirely to the graph and all remaining routing is deterministic. If the provider call fails, the node logs `interpret_provider_failed`, raises `DependencyUnavailableError`, and the `/chat` route returns HTTP 503 with a stable temporary-unavailable message.

---

### verify

**Input:** current verification state, the extracted operation, any identity fields found in this turn
**Changes:** updates verification state — adds a field, flags an invalid input, records a failure, marks verified, or locks the session
**Why it exists:** listing, confirming, and canceling appointments are protected operations. They must not run unless the patient has been matched by full name, phone, and date of birth.
**User-facing behavior:** prompts for missing fields one at a time, rejects invalid formats with a specific message, retries on identity mismatch, and locks the session after repeated failures.

This node also manages deferred operations. If the user originally asked for a protected action before being verified, that intent is stored in `deferred_operation`. Once verification succeeds, the graph continues to `execute_action` automatically to run it.

---

### execute_action

**Input:** the verified patient ID, the requested or deferred operation, and any stored appointment context
**Changes:** updates appointment state — stores the listed appointments, records the action result
**Why it exists:** this is where the actual business logic runs — fetching appointments, confirming, canceling, or returning help context.
**User-facing behavior:** produces the appointment list, confirmation result, cancellation result, or a help message.

`execute_action` only runs when verification already passed or was not required. It is skipped entirely if `verify` already set a turn output for the current turn.

---

## 4. Routing logic

After `interpret`, the graph asks: **is verification required for this operation, and is the user not yet verified?**

- If **yes** → route to `verify`
- If **no** → route to `execute_action`

Operations that require verification: `list_appointments`, `confirm_appointment`, `cancel_appointment`.

Operations that also route through `verify` even when the user hasn't explicitly asked to verify: `help`, `unknown`, `verify_identity`. These still pass through `verify` because the user may be in the middle of providing identity fields mid-flow.

After `verify`, the graph asks: **did `verify` produce any turn output?**

- If **yes** → the turn is complete. Graph ends.
- If **no** → `verify` completed silently (either verification succeeded, or it was not needed this sub-step). Graph continues to `execute_action`.

This means `execute_action` is skipped whenever `verify` already has the answer — for example, when prompting for a missing field, rejecting a bad format, or reporting a failed match. This avoids running appointment logic in the same turn as a verification prompt.

---

## 5. Deferred operation

When a user asks for a protected action before they have been verified, the system stores that intent and picks it back up automatically after verification succeeds.

**The user story:**

1. User: "I want to see my appointments"
2. Bot: "Please provide your full name"
3. User: "Ana Silva"
4. Bot: "Please provide your phone number"
5. User: "11999998888"
6. Bot: "Please provide your date of birth"
7. User: "1990-05-10"
8. Bot: *(verification succeeds, lists appointments automatically)*

The user never had to say "list appointments" a second time. The bot remembered what they were trying to do.

**How it works:** when `interpret` sees a protected operation from an unverified user, it saves that operation in `deferred_operation`. This field persists in the graph state across turns. Once `verify` completes the identity match, it finds `deferred_operation` still set, and the graph continues to `execute_action` to run it.

From the user's perspective, the bot is just "remembering" their original request. Technically, it is a state field that survives across turns until it gets consumed.

---

## 6. State model in practice

The graph maintains three kinds of state, with different lifespans:

**Turn output** (`state.turn`)
Ephemeral — reset at the start of every turn by `ingest`. Holds the result of the current turn: which response key to send, whether there was an issue, the operation result, the matched appointment. This is what `app/responses.py` reads to assemble the response message after the graph ends.

**Verification state** (`state.verification`)
Persists across turns. Stores whether the user is verified, how many failures they have had, their patient ID, and the individual identity fields they have provided so far. This accumulates across turns as the user provides their name, phone, and date of birth one message at a time.

**Appointment state** (`state.appointments`)
Persists across turns. Stores the last listed set of appointments and any appointment reference the user mentioned (e.g., "the first one"). This allows later turns to resolve references like "confirm the first one" without needing to re-list.

**Example across five turns:**

- Turn 1: user asks "show my appointments" → verification state is empty → `verify` prompts for name
- Turn 2: user says "Ana Silva" → `verify` stores `full_name`, prompts for phone
- Turn 3: user says "11999998888" → `verify` stores `phone`, prompts for DOB
- Turn 4: user says "1990-05-10" → `verify` matches identity, marks `verified`, `execute_action` runs the deferred list, stores returned appointments
- Turn 5: user says "confirm the first one" → verification state still shows verified, `execute_action` resolves "first one" from the stored appointment list

---

## 7. What the graph does not do

**It does not render final HTTP responses.** The graph ends with a populated `ConversationState`. Response messages are assembled from that state by `app/responses.py`, and HTTP shaping (status codes, JSON structure) is handled in `app/main.py`.

**It does not own the final wording of responses.** All response text is template-based and lives in `app/responses.py`. The graph only sets which `response_key` applies for the current turn.

**It does not let the LLM decide business policy.** The LLM classifies intent and extracts fields. It does not decide whether verification is required, which appointments the user owns, or whether a confirm or cancel is allowed. Those are all deterministic checks inside the graph nodes.

**It does not implement real authentication.** The identity match is a demo-level check against seeded in-memory patient data. It is not a production auth system.

**It does not replace domain services.** Appointment lookup, confirm, and cancel logic live in `app/services.py`. The graph calls those services from `execute_action`; it does not embed business logic directly in the node.

---

## 8. Example conversation mapped to graph transitions

### Example 1: First-time listing with full verification

**User:** "I want to see my appointments"

- `ingest`: clears turn output
- `interpret`: classifies `list_appointments`. User is not verified → stores `deferred_operation = list_appointments`. Routes to `verify`.
- `verify`: status is `unverified`. `full_name` is missing. Sets `response_key = collect_full_name`. Turn output is set → graph ends.
- *(bot asks for full name)*

**User:** "Ana Silva"

- `ingest`: clears turn output
- `interpret`: sees identity-shaped input, extracts `full_name = "Ana Silva"`. Routes to `verify`.
- `verify`: saves `full_name`. `phone` is still missing. Sets `response_key = collect_phone`. Graph ends.
- *(bot asks for phone number)*

**User:** "11999998888"

- `verify`: saves `phone`. `dob` is still missing. Sets `response_key = collect_dob`. Graph ends.
- *(bot asks for date of birth)*

**User:** "1990-05-10"

- `verify`: saves `dob`. All fields present → attempts identity match → match succeeds. Sets `verified = true`, stores `patient_id`. No turn output set. Graph continues to `execute_action`.
- `execute_action`: sees `deferred_operation = list_appointments`. Fetches appointments for the patient. Stores them in `state.appointments`. Sets `operation_result`. Graph ends.
- *(bot shows the appointment list)*

---

### Example 2: Invalid identity retry

**User:** "Maria Silva" *(wrong name for the phone and DOB combination)*

(Assuming phone and DOB were already provided in earlier turns)

- `verify`: all three fields are present → attempts identity match → match fails. Sets `response_key = verification_failed`, increments failure counter. Turn output is set → graph ends.
- *(bot says the identity could not be confirmed and invites a retry)*

If the user fails identity verification three times, the session is locked (`verification_status = locked`) and the bot returns `response_key = verification_locked` without accepting further identity input.

---

All routing decisions, state transitions, and policy checks shown in these examples are encoded in the graph nodes and conditional edges — not inside LLM output.
