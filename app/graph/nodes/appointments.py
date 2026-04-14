from __future__ import annotations

from dataclasses import asdict
from typing import Callable

from app.domain import policies
from app.domain.models import ActionResult, Appointment
from app.graph.routing import should_skip_action_execution
from app.graph.state import ConversationState
from app.observability import log_event


def make_list_node(appointment_service, logger):
    """Build the node that lists appointments for the verified patient."""

    def list_appointments(state: ConversationState) -> ConversationState:
        appointments = appointment_service.list_appointments(state["patient_id"])
        state["listed_appointments"] = appointments
        state["requested_action"] = "list_appointments"
        state["last_action_result"] = asdict(ActionResult("list_appointments", "listed"))
        state["response_text"] = _format_appointment_list(appointments)
        log_event(logger, "list_appointments", state, appointment_count=len(appointments))
        return state

    return list_appointments


def make_confirm_node(appointment_service, logger):
    """Build the node that confirms a selected appointment."""

    def confirm_appointment(state: ConversationState) -> ConversationState:
        appointment = _resolve_target_appointment(
            state,
            appointment_service,
            logger,
            action_name="confirm_appointment",
            missing_list_context_message="Please ask to see your appointments first, then tell me which one you want to confirm.",
            ambiguous_message="I couldn't tell which appointment you want to confirm. Please choose by number or date.",
        )
        if appointment is None:
            return state

        if not policies.can_confirm(appointment) and appointment.status.value != "confirmed":
            state["response_text"] = "I couldn't confirm that appointment. Please choose a scheduled appointment."
            state["error_code"] = "appointment_not_confirmable"
            log_event(logger, "confirm_appointment", state, outcome="not_confirmable")
            return state

        updated, action_result = appointment_service.confirm_appointment(state["patient_id"], appointment.id)
        state["last_action_result"] = asdict(action_result)
        state["listed_appointments"] = appointment_service.list_appointments(state["patient_id"])
        if action_result.outcome == "already_confirmed":
            state["response_text"] = f"That appointment was already confirmed for {updated.date} at {updated.time}."
        else:
            state["response_text"] = f"Your appointment for {updated.date} at {updated.time} is now confirmed."
        log_event(logger, "confirm_appointment", state, outcome=action_result.outcome, appointment_id=appointment.id)
        return state

    return confirm_appointment


def make_cancel_node(appointment_service, logger):
    """Build the node that cancels a selected appointment."""

    def cancel_appointment(state: ConversationState) -> ConversationState:
        appointment = _resolve_target_appointment(
            state,
            appointment_service,
            logger,
            action_name="cancel_appointment",
            missing_list_context_message="Please ask to see your appointments first, then tell me which one you want to cancel.",
            ambiguous_message="I couldn't tell which appointment you want to cancel. Please choose by number or date.",
        )
        if appointment is None:
            return state

        if not policies.can_cancel(appointment) and appointment.status.value != "canceled":
            state["response_text"] = "I couldn't cancel that appointment. Please choose a scheduled or confirmed appointment."
            state["error_code"] = "appointment_not_cancelable"
            log_event(logger, "cancel_appointment", state, outcome="not_cancelable")
            return state

        updated, action_result = appointment_service.cancel_appointment(state["patient_id"], appointment.id)
        state["last_action_result"] = asdict(action_result)
        state["listed_appointments"] = appointment_service.list_appointments(state["patient_id"])
        if action_result.outcome == "already_canceled":
            state["response_text"] = f"That appointment was already canceled for {updated.date} at {updated.time}."
        else:
            state["response_text"] = f"Your appointment for {updated.date} at {updated.time} has been canceled."
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
    """Build the node that executes the resolved action after verification."""

    def execute_action(state: ConversationState) -> ConversationState:
        if should_skip_action_execution(state):
            log_event(logger, "execute_action", state, outcome="skipped")
            return state
        action = state.get("requested_action")
        if action == "list_appointments":
            return list_node(state)
        if action == "confirm_appointment":
            return confirm_node(state)
        if action == "cancel_appointment":
            return cancel_node(state)
        return help_node(state)

    return execute_action


def _format_appointment_list(appointments) -> str:
    """Render appointment summaries into the deterministic fallback response."""
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
    action_name: str,
    missing_list_context_message: str,
    ambiguous_message: str,
) -> Appointment | None:
    """Resolve the appointment targeted by the current patient request."""
    listed_appointments = state.get("listed_appointments") or []
    reference = state.get("appointment_reference")
    if reference and reference.isdigit() and not listed_appointments:
        state["requested_action"] = action_name
        state["response_text"] = missing_list_context_message
        state["error_code"] = "missing_list_context"
        log_event(logger, "resolve_appointment_reference", state, outcome="missing_list_context")
        return None

    appointments = listed_appointments or appointment_service.list_appointments(state["patient_id"])
    appointment = policies.resolve_appointment_reference(reference, appointments)
    state["requested_action"] = action_name
    if appointment is None:
        state["response_text"] = ambiguous_message
        state["error_code"] = "ambiguous_appointment_reference"
        log_event(logger, "resolve_appointment_reference", state, outcome="ambiguous")
        return None

    if not policies.appointment_is_owned_by_patient(appointment, state.get("patient_id")):
        state["response_text"] = "I couldn't complete that request. Please choose one of your appointments."
        state["error_code"] = "appointment_not_owned"
        log_event(logger, action_name, state, outcome="not_owned")
        return None

    return appointment
