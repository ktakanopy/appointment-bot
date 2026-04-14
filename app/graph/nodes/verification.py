from __future__ import annotations

from app.domain import policies
from app.graph.routing import verification_required
from app.graph.state import ConversationState, turn_state, verification_state
from app.observability import log_event


PROMPTS = {
    "full_name": "I'm CAPY. I can help with that, but first I need to verify your identity. What is your full name?",
    "phone": "Thanks. What phone number is on your clinic record?",
    "dob": "Thanks. What is your date of birth? Use YYYY-MM-DD.",
}

INVALID_RESPONSES = {
    "full_name": ("That full name looks invalid. Please enter your first and last name.", "invalid_full_name"),
    "phone": ("That phone number looks invalid. Please enter at least 10 digits.", "invalid_phone"),
    "dob": ("That date of birth looks invalid. Please use YYYY-MM-DD.", "invalid_dob"),
}


def make_verification_node(verification_service, logger, max_verification_attempts: int):
    """Build the node that gates protected actions behind identity verification."""

    def verify(state: ConversationState) -> ConversationState:
        verification = verification_state(state)
        turn = turn_state(state)
        if not verification_required(state):
            return state

        if verification.get("verification_status") == "locked":
            return _set_locked_response(
                turn,
                logger,
                "For your security, this session is locked after too many failed verification attempts. Please start a new session.",
                state,
            )

        previous_status = verification.get("verification_status")
        missing_fields = policies.missing_verification_fields(state)

        if missing_fields:
            return _collect_missing_field(
                verification,
                turn,
                logger,
                field_name=missing_fields[0],
                previous_status=previous_status,
                state=state,
            )

        patient = verification_service.verify_identity(
            verification["provided_full_name"],
            verification["provided_phone"],
            verification["provided_dob"],
        )
        if patient is None:
            return _handle_failed_verification(
                verification,
                turn,
                logger,
                max_verification_attempts=max_verification_attempts,
                state=state,
            )

        return _handle_successful_verification(verification, turn, logger, patient_id=patient.id, state=state)

    return verify


def _set_locked_response(
    turn: dict,
    logger,
    response_text: str,
    state: ConversationState,
) -> ConversationState:
    turn["requested_action"] = "verify_identity"
    turn["response_text"] = response_text
    turn["error_code"] = "verification_locked"
    log_event(logger, "verify_identity", state, outcome="locked")
    return state


def _collect_missing_field(
    verification: dict,
    turn: dict,
    logger,
    *,
    field_name: str,
    previous_status: str | None,
    state: ConversationState,
) -> ConversationState:
    verification["verification_status"] = "collecting"
    turn["requested_action"] = "verify_identity"
    invalid_response = _invalid_response_for_field(state, field_name, previous_status)
    if invalid_response is None:
        turn["response_text"] = PROMPTS[field_name]
        turn["error_code"] = None
    else:
        turn["response_text"], turn["error_code"] = invalid_response
    log_event(logger, "collect_missing_verification_fields", state)
    return state


def _handle_failed_verification(
    verification: dict,
    turn: dict,
    logger,
    *,
    max_verification_attempts: int,
    state: ConversationState,
) -> ConversationState:
    verification["verification_failures"] = verification.get("verification_failures", 0) + 1
    verification["verification_status"] = "failed"
    verification["verified"] = False
    verification["patient_id"] = None
    verification["provided_full_name"] = None
    verification["provided_phone"] = None
    verification["provided_dob"] = None
    turn["requested_action"] = "verify_identity"
    if verification["verification_failures"] >= max_verification_attempts:
        verification["verification_status"] = "locked"
        return _set_locked_response(
            turn,
            logger,
            "I couldn't verify your identity. For your security, this session is now locked. Please start a new session to try again.",
            state,
        )
    turn["response_text"] = "I couldn't verify your identity because the provided name, phone number, and date of birth do not match our records. Let's try again. What is your full name?"
    turn["error_code"] = "invalid_identity"
    log_event(logger, "verify_identity", state, outcome="failed")
    return state


def _handle_successful_verification(
    verification: dict,
    turn: dict,
    logger,
    *,
    patient_id: str,
    state: ConversationState,
) -> ConversationState:
    verification["verification_status"] = "verified"
    verification["verified"] = True
    verification["verification_failures"] = 0
    verification["patient_id"] = patient_id
    turn["error_code"] = None
    if turn.get("deferred_action"):
        turn["requested_action"] = turn["deferred_action"]
        turn["deferred_action"] = None
    log_event(logger, "verify_identity", state, outcome="verified")
    return state


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
