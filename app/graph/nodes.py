from __future__ import annotations

from collections.abc import Callable

from app.graph.parsing import (
    extract_dob,
    extract_full_name,
    extract_phone,
    normalize_dob,
    normalize_full_name,
    normalize_phone,
    resolve_appointment_reference,
)
from app.graph.routing import should_skip_action_execution, verification_required
from app.graph.state import (
    AppointmentState,
    ConversationState,
    TurnState,
    VerificationState,
    appointment_state,
    turn_state,
    verification_state,
)
from app.models import (
    ActionOutcome,
    Appointment,
    AppointmentNotCancelableError,
    AppointmentNotConfirmableError,
    AppointmentNotFoundError,
    AppointmentNotOwnedError,
    ConversationOperation,
    ConversationOperationResult,
    ResponseKey,
    TurnIssue,
    VerificationStatus,
)
from app.observability import log_event

APPOINTMENT_ACTIONS = {
    ConversationOperation.CONFIRM_APPOINTMENT,
    ConversationOperation.CANCEL_APPOINTMENT,
}

MESSAGE_HISTORY_LIMIT = 6

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


def make_ingest_node(logger):
    def ingest(state: ConversationState) -> ConversationState:
        turn = turn_state(state)
        message = (state.incoming_message or "").strip()
        turn.reset_turn_output()
        if message:
            state.add_user_message(message)
        log_event(logger, "ingest_user_message", state)
        return state

    return ingest


def make_interpret_node(logger, provider):
    def interpret(state: ConversationState) -> ConversationState:
        message = (state.incoming_message or "").strip()
        verification = verification_state(state)
        turn = turn_state(state)
        appointments = appointment_state(state)
        provider_state = {
            "verification": {"verified": verification.verified},
            "turn": {
                "requested_operation": turn.requested_operation.value,
                "deferred_operation": (
                    turn.deferred_operation.value if turn.deferred_operation is not None else None
                ),
            },
            "missing_verification_fields": verification.missing_fields(),
            "messages": state.recent_messages(MESSAGE_HISTORY_LIMIT),
        }
        result = provider.interpret(message, provider_state)
        requested_operation = result.requested_operation

        verification.fill_missing_fields(
            phone=normalize_phone(result.phone),
            dob=normalize_dob(result.dob),
            full_name=normalize_full_name(result.full_name),
        )

        turn.requested_operation = requested_operation
        _update_deferred_operation(verification, turn, requested_operation)
        _update_appointment_reference(appointments, requested_operation, result.appointment_reference)
        log_event(
            logger,
            "parse_intent_and_entities",
            state,
            appointment_reference=appointments.appointment_reference,
        )
        return state

    return interpret


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


def make_list_node(appointment_service, logger):
    def list_appointments(state: ConversationState) -> ConversationState:
        verification = verification_state(state)
        appointments_state = appointment_state(state)
        turn = turn_state(state)
        appointments = appointment_service.list_appointments(verification.patient_id)
        appointments_state.listed_appointments = appointments
        turn.requested_operation = ConversationOperation.LIST_APPOINTMENTS
        turn.operation_result = ConversationOperationResult(
            operation=ConversationOperation.LIST_APPOINTMENTS,
            outcome=ActionOutcome.LISTED,
        )
        turn.response_key = ResponseKey.APPOINTMENTS_LIST
        turn.issue = None
        log_event(logger, "list_appointments", state, appointment_count=len(appointments))
        return state

    return list_appointments


def make_confirm_node(appointment_service, logger):
    def confirm_appointment(state: ConversationState) -> ConversationState:
        verification = verification_state(state)
        appointments_state = appointment_state(state)
        turn = turn_state(state)
        appointment = _resolve_target_appointment(
            state,
            appointment_service,
            logger,
            operation=ConversationOperation.CONFIRM_APPOINTMENT,
            missing_list_context_key=ResponseKey.CONFIRM_MISSING_LIST_CONTEXT,
            ambiguous_key=ResponseKey.CONFIRM_AMBIGUOUS_REFERENCE,
        )
        if appointment is None:
            return state

        try:
            updated, outcome = appointment_service.confirm_appointment(verification.patient_id, appointment.id)
        except AppointmentNotConfirmableError:
            turn.response_key = ResponseKey.CONFIRM_NOT_ALLOWED
            turn.issue = TurnIssue.APPOINTMENT_NOT_CONFIRMABLE
            log_event(logger, "confirm_appointment", state, outcome="not_confirmable")
            return state
        except AppointmentNotOwnedError:
            turn.response_key = ResponseKey.APPOINTMENT_NOT_OWNED
            turn.issue = TurnIssue.APPOINTMENT_NOT_OWNED
            log_event(logger, "confirm_appointment", state, outcome="not_owned")
            return state
        except AppointmentNotFoundError:
            turn.response_key = ResponseKey.APPOINTMENT_NOT_FOUND
            turn.issue = TurnIssue.APPOINTMENT_NOT_FOUND
            log_event(logger, "confirm_appointment", state, outcome="not_found")
            return state
        turn.response_key = (
            ResponseKey.CONFIRM_ALREADY_CONFIRMED
            if outcome == ActionOutcome.ALREADY_CONFIRMED
            else ResponseKey.CONFIRM_SUCCESS
        )
        turn.issue = None
        turn.subject_appointment = updated
        turn.operation_result = ConversationOperationResult(
            operation=ConversationOperation.CONFIRM_APPOINTMENT,
            outcome=outcome,
            appointment_id=appointment.id,
        )
        appointments_state.listed_appointments = appointment_service.list_appointments(verification.patient_id)
        log_event(logger, "confirm_appointment", state, outcome=outcome.value, appointment_id=appointment.id)
        return state

    return confirm_appointment


def make_cancel_node(appointment_service, logger):
    def cancel_appointment(state: ConversationState) -> ConversationState:
        verification = verification_state(state)
        appointments_state = appointment_state(state)
        turn = turn_state(state)
        appointment = _resolve_target_appointment(
            state,
            appointment_service,
            logger,
            operation=ConversationOperation.CANCEL_APPOINTMENT,
            missing_list_context_key=ResponseKey.CANCEL_MISSING_LIST_CONTEXT,
            ambiguous_key=ResponseKey.CANCEL_AMBIGUOUS_REFERENCE,
        )
        if appointment is None:
            return state

        try:
            updated, outcome = appointment_service.cancel_appointment(verification.patient_id, appointment.id)
        except AppointmentNotCancelableError:
            turn.response_key = ResponseKey.CANCEL_NOT_ALLOWED
            turn.issue = TurnIssue.APPOINTMENT_NOT_CANCELABLE
            log_event(logger, "cancel_appointment", state, outcome="not_cancelable")
            return state
        except AppointmentNotOwnedError:
            turn.response_key = ResponseKey.APPOINTMENT_NOT_OWNED
            turn.issue = TurnIssue.APPOINTMENT_NOT_OWNED
            log_event(logger, "cancel_appointment", state, outcome="not_owned")
            return state
        except AppointmentNotFoundError:
            turn.response_key = ResponseKey.APPOINTMENT_NOT_FOUND
            turn.issue = TurnIssue.APPOINTMENT_NOT_FOUND
            log_event(logger, "cancel_appointment", state, outcome="not_found")
            return state
        turn.response_key = (
            ResponseKey.CANCEL_ALREADY_CANCELED
            if outcome == ActionOutcome.ALREADY_CANCELED
            else ResponseKey.CANCEL_SUCCESS
        )
        turn.issue = None
        turn.subject_appointment = updated
        turn.operation_result = ConversationOperationResult(
            operation=ConversationOperation.CANCEL_APPOINTMENT,
            outcome=outcome,
            appointment_id=appointment.id,
        )
        appointments_state.listed_appointments = appointment_service.list_appointments(verification.patient_id)
        log_event(logger, "cancel_appointment", state, outcome=outcome.value, appointment_id=appointment.id)
        return state

    return cancel_appointment


def make_help_node(logger):
    def help_or_unknown(state: ConversationState) -> ConversationState:
        verification = verification_state(state)
        turn = turn_state(state)
        turn.requested_operation = ConversationOperation.HELP
        if verification.verified:
            turn.response_key = ResponseKey.HELP_VERIFIED
        else:
            turn.response_key = ResponseKey.HELP_UNVERIFIED
        log_event(logger, "handle_help_or_unknown", state)
        return state

    return help_or_unknown


def make_execute_action_node(
    logger,
    *,
    list_node: Callable[[ConversationState], ConversationState],
    confirm_node: Callable[[ConversationState], ConversationState],
    cancel_node: Callable[[ConversationState], ConversationState],
    help_node: Callable[[ConversationState], ConversationState],
):
    def execute_action(state: ConversationState) -> ConversationState:
        if should_skip_action_execution(state):
            log_event(logger, "execute_action", state, outcome="skipped")
            return state
        operation = turn_state(state).requested_operation
        if operation == ConversationOperation.LIST_APPOINTMENTS:
            return list_node(state)
        if operation == ConversationOperation.CONFIRM_APPOINTMENT:
            return confirm_node(state)
        if operation == ConversationOperation.CANCEL_APPOINTMENT:
            return cancel_node(state)
        return help_node(state)

    return execute_action


def _update_deferred_operation(
    verification: VerificationState,
    turn: TurnState,
    requested_operation: ConversationOperation,
) -> None:
    if verification.verified or not requested_operation.requires_verification:
        return
    if turn.deferred_operation is None:
        turn.deferred_operation = requested_operation


def _update_appointment_reference(
    appointments: AppointmentState,
    requested_operation: ConversationOperation,
    appointment_reference: str | None,
) -> None:
    if requested_operation not in APPOINTMENT_ACTIONS:
        appointments.appointment_reference = None
        return
    if appointment_reference:
        appointments.appointment_reference = appointment_reference


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


def _resolve_target_appointment(
    state: ConversationState,
    appointment_service,
    logger,
    *,
    operation: ConversationOperation,
    missing_list_context_key: ResponseKey,
    ambiguous_key: ResponseKey,
) -> Appointment | None:
    appointments_state = appointment_state(state)
    turn = turn_state(state)
    verification = verification_state(state)
    listed_appointments = appointments_state.listed_appointments or []
    reference = appointments_state.appointment_reference
    if reference and reference.isdigit() and not listed_appointments:
        turn.requested_operation = operation
        turn.response_key = missing_list_context_key
        turn.issue = TurnIssue.MISSING_LIST_CONTEXT
        log_event(logger, "resolve_appointment_reference", state, outcome="missing_list_context")
        return None

    appointments = listed_appointments or appointment_service.list_appointments(verification.patient_id)
    appointment = resolve_appointment_reference(reference, appointments)
    turn.requested_operation = operation
    if appointment is None:
        turn.response_key = ambiguous_key
        turn.issue = TurnIssue.AMBIGUOUS_APPOINTMENT_REFERENCE
        log_event(logger, "resolve_appointment_reference", state, outcome="ambiguous")
        return None

    return appointment
