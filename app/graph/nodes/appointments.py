from __future__ import annotations

from dataclasses import asdict

from app.domain import policies
from app.domain.models import ActionResult
from app.graph.state import ConversationState, ensure_state_defaults
from app.observability import log_event


def _serialize_appointments(appointments):
    return [
        {
            "id": appointment.id,
            "date": appointment.date,
            "time": appointment.time,
            "doctor": appointment.doctor,
            "status": appointment.status.value,
        }
        for appointment in appointments
    ]


def make_list_node(appointment_service, logger):
    def list_appointments(state: ConversationState) -> ConversationState:
        state = ensure_state_defaults(state)
        appointments = appointment_service.list_appointments(state["patient_id"])
        state["listed_appointments"] = appointments
        state["requested_action"] = "list_appointments"
        state["last_action_result"] = asdict(ActionResult("list_appointments", "listed"))
        state["response_text"] = _format_appointment_list(appointments)
        log_event(logger, "list_appointments", state, appointment_count=len(appointments))
        return state

    return list_appointments


def make_confirm_node(appointment_service, logger):
    def confirm_appointment(state: ConversationState) -> ConversationState:
        state = ensure_state_defaults(state)
        listed_appointments = state.get("listed_appointments") or []
        reference = state.get("appointment_reference")
        if reference and reference.isdigit() and not listed_appointments:
            state["response_text"] = "Please ask to see your appointments first, then tell me which one you want to confirm."
            state["error_code"] = "missing_list_context"
            log_event(logger, "resolve_appointment_reference", state, outcome="missing_list_context")
            return state

        appointments = listed_appointments or appointment_service.list_appointments(state["patient_id"])
        appointment = policies.resolve_appointment_reference(reference, appointments)
        state["requested_action"] = "confirm_appointment"
        if appointment is None:
            state["response_text"] = "I couldn't tell which appointment you want to confirm. Please choose by number or date."
            state["error_code"] = "ambiguous_appointment_reference"
            log_event(logger, "resolve_appointment_reference", state, outcome="ambiguous")
            return state

        if not policies.appointment_is_owned_by_patient(appointment, state.get("patient_id")):
            state["response_text"] = "I couldn't complete that request. Please choose one of your appointments."
            state["error_code"] = "appointment_not_owned"
            log_event(logger, "confirm_appointment", state, outcome="not_owned")
            return state

        if not policies.can_confirm(appointment) and appointment.status.value != "confirmed":
            state["response_text"] = "I couldn't confirm that appointment. Please choose a scheduled appointment."
            state["error_code"] = "appointment_not_confirmable"
            log_event(logger, "confirm_appointment", state, outcome="not_confirmable")
            return state

        updated, action_result = appointment_service.confirm_appointment(state["patient_id"], appointment.id)
        state["selected_appointment_id"] = appointment.id
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
    def cancel_appointment(state: ConversationState) -> ConversationState:
        state = ensure_state_defaults(state)
        listed_appointments = state.get("listed_appointments") or []
        reference = state.get("appointment_reference")
        if reference and reference.isdigit() and not listed_appointments:
            state["response_text"] = "Please ask to see your appointments first, then tell me which one you want to cancel."
            state["error_code"] = "missing_list_context"
            log_event(logger, "resolve_appointment_reference", state, outcome="missing_list_context")
            return state

        appointments = listed_appointments or appointment_service.list_appointments(state["patient_id"])
        appointment = policies.resolve_appointment_reference(reference, appointments)
        state["requested_action"] = "cancel_appointment"
        if appointment is None:
            state["response_text"] = "I couldn't tell which appointment you want to cancel. Please choose by number or date."
            state["error_code"] = "ambiguous_appointment_reference"
            log_event(logger, "resolve_appointment_reference", state, outcome="ambiguous")
            return state

        if not policies.appointment_is_owned_by_patient(appointment, state.get("patient_id")):
            state["response_text"] = "I couldn't complete that request. Please choose one of your appointments."
            state["error_code"] = "appointment_not_owned"
            log_event(logger, "cancel_appointment", state, outcome="not_owned")
            return state

        if not policies.can_cancel(appointment) and appointment.status.value != "canceled":
            state["response_text"] = "I couldn't cancel that appointment. Please choose a scheduled or confirmed appointment."
            state["error_code"] = "appointment_not_cancelable"
            log_event(logger, "cancel_appointment", state, outcome="not_cancelable")
            return state

        updated, action_result = appointment_service.cancel_appointment(state["patient_id"], appointment.id)
        state["selected_appointment_id"] = appointment.id
        state["last_action_result"] = asdict(action_result)
        state["listed_appointments"] = appointment_service.list_appointments(state["patient_id"])
        if action_result.outcome == "already_canceled":
            state["response_text"] = f"That appointment was already canceled for {updated.date} at {updated.time}."
        else:
            state["response_text"] = f"Your appointment for {updated.date} at {updated.time} has been canceled."
        log_event(logger, "cancel_appointment", state, outcome=action_result.outcome, appointment_id=appointment.id)
        return state

    return cancel_appointment


def _format_appointment_list(appointments) -> str:
    if not appointments:
        return "You do not have any appointments right now."

    lines = ["Here are your appointments:"]
    for index, appointment in enumerate(appointments, start=1):
        lines.append(
            f"{index}. {appointment.date} at {appointment.time} with {appointment.doctor} ({appointment.status.value})"
        )
    return "\n".join(lines)
