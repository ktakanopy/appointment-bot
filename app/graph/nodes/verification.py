from __future__ import annotations

from app.domain import policies
from app.graph.state import ConversationState
from app.observability import log_event


PROMPTS = {
    "full_name": "I can help with that, but first I need to verify your identity. What is your full name?",
    "phone": "Thanks. What phone number is on your clinic record?",
    "dob": "Thanks. What is your date of birth? Use YYYY-MM-DD.",
}

INVALID_RESPONSES = {
    "full_name": ("That full name looks invalid. Please enter your first and last name.", "invalid_full_name"),
    "phone": ("That phone number looks invalid. Please enter at least 10 digits.", "invalid_phone"),
    "dob": ("That date of birth looks invalid. Please use YYYY-MM-DD.", "invalid_dob"),
}


def make_verification_node(verification_service, logger, max_verification_attempts: int):
    def verify(state: ConversationState) -> ConversationState:
        if state.get("verification_locked"):
            state["verification_status"] = "locked"
            state["requested_action"] = "verify_identity"
            state["response_text"] = "For your security, this session is locked after too many failed verification attempts. Please start a new session."
            state["error_code"] = "verification_locked"
            log_event(logger, "verify_identity", state, outcome="locked")
            return state

        previous_status = state.get("verification_status")
        state["missing_verification_fields"] = policies.missing_verification_fields(state)

        if state["missing_verification_fields"]:
            next_field = state["missing_verification_fields"][0]
            state["verification_status"] = "collecting"
            state["requested_action"] = "verify_identity"
            invalid_response = _invalid_response_for_field(state, next_field, previous_status)
            if invalid_response is None:
                state["response_text"] = PROMPTS[next_field]
                state["error_code"] = None
            else:
                state["response_text"], state["error_code"] = invalid_response
            log_event(logger, "collect_missing_verification_fields", state)
            return state

        patient = verification_service.verify_identity(
            state["provided_full_name"],
            state["provided_phone"],
            state["provided_dob"],
        )
        if patient is None:
            state["verification_failures"] = state.get("verification_failures", 0) + 1
            state["verification_status"] = "failed"
            state["verified"] = False
            state["patient_id"] = None
            state["provided_full_name"] = None
            state["provided_phone"] = None
            state["provided_dob"] = None
            state["missing_verification_fields"] = ["full_name", "phone", "dob"]
            state["requested_action"] = "verify_identity"
            if state["verification_failures"] >= max_verification_attempts:
                state["verification_status"] = "locked"
                state["verification_locked"] = True
                state["response_text"] = "I couldn't verify your identity. For your security, this session is now locked. Please start a new session to try again."
                state["error_code"] = "verification_locked"
                log_event(logger, "verify_identity", state, outcome="locked")
                return state
            state["response_text"] = "I couldn't verify your identity because the provided name, phone number, and date of birth do not match our records. Let's try again. What is your full name?"
            state["error_code"] = "invalid_identity"
            log_event(logger, "verify_identity", state, outcome="failed")
            return state

        state["verification_status"] = "verified"
        state["verified"] = True
        state["verification_failures"] = 0
        state["verification_locked"] = False
        state["patient_id"] = patient.id
        state["error_code"] = None
        if state.get("deferred_action"):
            state["requested_action"] = state["deferred_action"]
            state["deferred_action"] = None
        log_event(logger, "verify_identity", state, outcome="verified")
        return state

    return verify


def _invalid_response_for_field(
    state: ConversationState,
    field_name: str,
    previous_status: str | None,
) -> tuple[str, str] | None:
    if previous_status not in {"collecting", "failed"}:
        return None
    message = (state.get("incoming_message") or "").strip()
    if not message:
        return None
    parsed_name = policies.extract_full_name(message)
    parsed_phone = policies.extract_phone(message)
    parsed_dob = policies.extract_dob(message)
    if field_name == "full_name" and parsed_name is None and parsed_phone is None and parsed_dob is None:
        return INVALID_RESPONSES[field_name]
    if field_name == "phone" and parsed_phone is None and parsed_name is None and parsed_dob is None:
        return INVALID_RESPONSES[field_name]
    if field_name == "dob" and parsed_dob is None and parsed_name is None and parsed_phone is None:
        return INVALID_RESPONSES[field_name]
    return None
