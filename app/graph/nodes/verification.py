from __future__ import annotations

from app.domain import policies
from app.graph.state import ConversationState
from app.observability import log_event


PROMPTS = {
    "full_name": "I can help with that, but first I need to verify your identity. What is your full name?",
    "phone": "Thanks. What phone number is on your clinic record?",
    "dob": "Thanks. What is your date of birth? Use YYYY-MM-DD.",
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

        state["missing_verification_fields"] = policies.missing_verification_fields(state)

        if state["missing_verification_fields"]:
            next_field = state["missing_verification_fields"][0]
            state["verification_status"] = "collecting"
            state["requested_action"] = "verify_identity"
            state["response_text"] = PROMPTS[next_field]
            state["error_code"] = None
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
            state["response_text"] = "I couldn't verify your identity with those details. Let's try again. What is your full name?"
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
