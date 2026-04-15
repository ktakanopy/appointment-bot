from __future__ import annotations

from typing import Callable

from app.domain.actions import Action
from app.domain.errors import AppointmentNotCancelableError, AppointmentNotConfirmableError, AppointmentNotOwnedError
from app.domain.models import ActionResult, Appointment
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
        turn.requested_action = Action.LIST_APPOINTMENTS
        turn.last_action_result = ActionResult("list_appointments", "listed").model_dump()
        turn.response_text = _format_appointment_list(appointments)
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
            action_name=Action.CONFIRM_APPOINTMENT,
            missing_list_context_message="Please ask to see your appointments first, then tell me which one you want to confirm.",
            ambiguous_message="I couldn't tell which appointment you want to confirm. Please choose by number or date.",
        )
        if appointment is None:
            return state

        try:
            updated, action_result = appointment_service.confirm_appointment(verification.patient_id, appointment.id)
        except AppointmentNotConfirmableError:
            turn.response_text = "I couldn't confirm that appointment. Please choose a scheduled appointment."
            turn.error_code = "appointment_not_confirmable"
            log_event(logger, "confirm_appointment", state, outcome="not_confirmable")
            return state
        except AppointmentNotOwnedError:
            turn.response_text = "I couldn't complete that request. Please choose one of your appointments."
            turn.error_code = "appointment_not_owned"
            log_event(logger, "confirm_appointment", state, outcome="not_owned")
            return state
        turn.last_action_result = action_result.model_dump()
        appointments_state.listed_appointments = appointment_service.list_appointments(verification.patient_id)
        if action_result.outcome == "already_confirmed":
            turn.response_text = f"That appointment was already confirmed for {updated.date} at {updated.time}."
        else:
            turn.response_text = f"Your appointment for {updated.date} at {updated.time} is now confirmed."
        log_event(logger, "confirm_appointment", state, outcome=action_result.outcome, appointment_id=appointment.id)
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
            action_name=Action.CANCEL_APPOINTMENT,
            missing_list_context_message="Please ask to see your appointments first, then tell me which one you want to cancel.",
            ambiguous_message="I couldn't tell which appointment you want to cancel. Please choose by number or date.",
        )
        if appointment is None:
            return state

        try:
            updated, action_result = appointment_service.cancel_appointment(verification.patient_id, appointment.id)
        except AppointmentNotCancelableError:
            turn.response_text = "I couldn't cancel that appointment. Please choose a scheduled or confirmed appointment."
            turn.error_code = "appointment_not_cancelable"
            log_event(logger, "cancel_appointment", state, outcome="not_cancelable")
            return state
        except AppointmentNotOwnedError:
            turn.response_text = "I couldn't complete that request. Please choose one of your appointments."
            turn.error_code = "appointment_not_owned"
            log_event(logger, "cancel_appointment", state, outcome="not_owned")
            return state
        turn.last_action_result = action_result.model_dump()
        appointments_state.listed_appointments = appointment_service.list_appointments(verification.patient_id)
        if action_result.outcome == "already_canceled":
            turn.response_text = f"That appointment was already canceled for {updated.date} at {updated.time}."
        else:
            turn.response_text = f"Your appointment for {updated.date} at {updated.time} has been canceled."
        log_event(logger, "cancel_appointment", state, outcome=action_result.outcome, appointment_id=appointment.id)
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
        action = turn_state(state).requested_action
        if action == Action.LIST_APPOINTMENTS:
            return list_node(state)
        if action == Action.CONFIRM_APPOINTMENT:
            return confirm_node(state)
        if action == Action.CANCEL_APPOINTMENT:
            return cancel_node(state)
        return help_node(state)

    return execute_action


def _format_appointment_list(appointments) -> str:
    if not appointments:
        return "You do not have any appointments right now."

    lines = ["Here are your appointments:"]
    for index, appointment in enumerate(appointments, start=1):
        lines.append(
            f"{index}. {appointment.date} at {appointment.time} with {appointment.doctor} ({appointment.status.value})"
        )
    return "\n".join(lines)


def _resolve_target_appointment(
    state: ConversationState,
    appointment_service,
    logger,
    *,
    action_name: Action,
    missing_list_context_message: str,
    ambiguous_message: str,
) -> Appointment | None:
    appointments_state = appointment_state(state)
    turn = turn_state(state)
    verification = verification_state(state)
    listed_appointments = appointments_state.listed_appointments or []
    reference = appointments_state.appointment_reference
    if reference and reference.isdigit() and not listed_appointments:
        turn.requested_action = action_name
        turn.response_text = missing_list_context_message
        turn.error_code = "missing_list_context"
        log_event(logger, "resolve_appointment_reference", state, outcome="missing_list_context")
        return None

    appointments = listed_appointments or appointment_service.list_appointments(verification.patient_id)
    appointment = resolve_appointment_reference(reference, appointments)
    turn.requested_action = action_name
    if appointment is None:
        turn.response_text = ambiguous_message
        turn.error_code = "ambiguous_appointment_reference"
        log_event(logger, "resolve_appointment_reference", state, outcome="ambiguous")
        return None

    return appointment
