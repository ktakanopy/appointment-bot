from __future__ import annotations

from app.application.contracts.conversation import (
    ConversationOperation,
    ResponseKey,
    TurnIssue,
    VerificationStatus,
)
from app.graph.routing import verification_required
from app.graph.state import ConversationState, TurnState, VerificationState, turn_state, verification_state
from app.graph.text_extraction import extract_dob, extract_full_name, extract_phone
from app.observability import log_event

PROMPTS = {
    "full_name": ResponseKey.COLLECT_FULL_NAME,
    "phone": ResponseKey.COLLECT_PHONE,
    "dob": ResponseKey.COLLECT_DOB,
}

INVALID_RESPONSES = {
    "full_name": (ResponseKey.INVALID_FULL_NAME, TurnIssue.INVALID_FULL_NAME),
    "phone": (ResponseKey.INVALID_PHONE, TurnIssue.INVALID_PHONE),
    "dob": (ResponseKey.INVALID_DOB, TurnIssue.INVALID_DOB),
}


def make_verification_node(verification_service, logger, max_verification_attempts: int):
    def verify(state: ConversationState) -> ConversationState:
        verification = verification_state(state)
        turn = turn_state(state)
        if not verification_required(state):
            return state

        if verification.verification_status == VerificationStatus.LOCKED:
            return _set_locked_response(turn, logger, state)

        previous_status = verification.verification_status
        missing_field = verification.next_missing_field()

        if missing_field:
            return _collect_missing_field(
                verification,
                turn,
                logger,
                field_name=missing_field,
                previous_status=previous_status,
                state=state,
            )

        patient = verification_service.verify_identity(
            verification.provided_full_name,
            verification.provided_phone,
            verification.provided_dob,
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
    turn: TurnState,
    logger,
    state: ConversationState,
) -> ConversationState:
    turn.requested_operation = ConversationOperation.VERIFY_IDENTITY
    turn.response_key = ResponseKey.VERIFICATION_LOCKED
    turn.issue = TurnIssue.VERIFICATION_LOCKED
    log_event(logger, "verify_identity", state, outcome="locked")
    return state


def _collect_missing_field(
    verification: VerificationState,
    turn: TurnState,
    logger,
    *,
    field_name: str,
    previous_status: VerificationStatus,
    state: ConversationState,
) -> ConversationState:
    verification.mark_collecting()
    turn.requested_operation = ConversationOperation.VERIFY_IDENTITY
    invalid_response = _invalid_response_for_field(state, field_name, previous_status)
    if invalid_response is None:
        turn.response_key = PROMPTS[field_name]
        turn.issue = None
    else:
        turn.response_key, turn.issue = invalid_response
    log_event(logger, "collect_missing_verification_fields", state)
    return state


def _handle_failed_verification(
    verification: VerificationState,
    turn: TurnState,
    logger,
    *,
    max_verification_attempts: int,
    state: ConversationState,
) -> ConversationState:
    verification.verification_failures += 1
    verification.reset_failed_verification()
    turn.requested_operation = ConversationOperation.VERIFY_IDENTITY
    if verification.verification_failures >= max_verification_attempts:
        verification.verification_status = VerificationStatus.LOCKED
        return _set_locked_response(turn, logger, state)
    turn.response_key = ResponseKey.VERIFICATION_FAILED
    turn.issue = TurnIssue.INVALID_IDENTITY
    log_event(logger, "verify_identity", state, outcome="failed")
    return state


def _handle_successful_verification(
    verification: VerificationState,
    turn: TurnState,
    logger,
    *,
    patient_id: str,
    state: ConversationState,
) -> ConversationState:
    had_deferred_operation = turn.deferred_operation is not None
    verification.mark_verified(patient_id)
    turn.issue = None
    turn.response_key = None
    turn.resume_deferred_operation()
    if not had_deferred_operation:
        turn.requested_operation = ConversationOperation.LIST_APPOINTMENTS
    log_event(logger, "verify_identity", state, outcome="verified")
    return state


def _invalid_response_for_field(
    state: ConversationState,
    field_name: str,
    previous_status: VerificationStatus,
) -> tuple[ResponseKey, TurnIssue] | None:
    if previous_status not in {VerificationStatus.COLLECTING, VerificationStatus.FAILED}:
        return None
    message = (state.incoming_message or "").strip()
    if not message:
        return None
    parsed_name = extract_full_name(message)
    parsed_phone = extract_phone(message)
    parsed_dob = extract_dob(message)
    if field_name == "full_name" and parsed_name is None and parsed_phone is None and parsed_dob is None:
        return INVALID_RESPONSES[field_name]
    if field_name == "phone" and parsed_phone is None and parsed_name is None and parsed_dob is None:
        return INVALID_RESPONSES[field_name]
    if field_name == "dob" and parsed_dob is None and parsed_name is None and parsed_phone is None:
        return INVALID_RESPONSES[field_name]
    return None
