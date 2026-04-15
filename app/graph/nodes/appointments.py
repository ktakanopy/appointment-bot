from __future__ import annotations

from typing import Callable

from app.application.contracts.conversation import (
    ConversationOperation,
    ConversationOperationOutcome,
    ConversationOperationResult,
    ResponseKey,
    TurnIssue,
)
from app.domain.errors import (
    AppointmentNotCancelableError,
    AppointmentNotConfirmableError,
    AppointmentNotFoundError,
    AppointmentNotOwnedError,
)
from app.domain.models import Appointment, AppointmentMutationOutcome
from app.graph.routing import should_skip_action_execution
from app.graph.state import AppointmentState, ConversationState, TurnState, VerificationState, appointment_state, turn_state, verification_state
from app.graph.text_extraction import resolve_appointment_reference
from app.observability import log_event


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
            outcome=ConversationOperationOutcome.LISTED,
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
            if outcome == AppointmentMutationOutcome.ALREADY_CONFIRMED
            else ResponseKey.CONFIRM_SUCCESS
        )
        turn.issue = None
        turn.subject_appointment = updated
        turn.operation_result = ConversationOperationResult(
            operation=ConversationOperation.CONFIRM_APPOINTMENT,
            outcome=_map_mutation_outcome(outcome),
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
            if outcome == AppointmentMutationOutcome.ALREADY_CANCELED
            else ResponseKey.CANCEL_SUCCESS
        )
        turn.issue = None
        turn.subject_appointment = updated
        turn.operation_result = ConversationOperationResult(
            operation=ConversationOperation.CANCEL_APPOINTMENT,
            outcome=_map_mutation_outcome(outcome),
            appointment_id=appointment.id,
        )
        appointments_state.listed_appointments = appointment_service.list_appointments(verification.patient_id)
        log_event(logger, "cancel_appointment", state, outcome=outcome.value, appointment_id=appointment.id)
        return state

    return cancel_appointment


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
def _map_mutation_outcome(outcome: AppointmentMutationOutcome) -> ConversationOperationOutcome:
    if outcome == AppointmentMutationOutcome.CONFIRMED:
        return ConversationOperationOutcome.CONFIRMED
    if outcome == AppointmentMutationOutcome.ALREADY_CONFIRMED:
        return ConversationOperationOutcome.ALREADY_CONFIRMED
    if outcome == AppointmentMutationOutcome.CANCELED:
        return ConversationOperationOutcome.CANCELED
    return ConversationOperationOutcome.ALREADY_CANCELED
