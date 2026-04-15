from __future__ import annotations

from app.graph.state import ConversationState
from app.models import (
    ChatTurnResponse,
    ConversationOperation,
    ResponseKey,
)

STATIC_RESPONSES: dict[ResponseKey, str] = {
    ResponseKey.COLLECT_FULL_NAME: "I'm CAPY. I can help you list, confirm, and cancel appointments, but first you need to identify yourself. What is your full name?",
    ResponseKey.COLLECT_PHONE: "Thanks. What phone number is on your clinic record?",
    ResponseKey.COLLECT_DOB: "Thanks. What is your date of birth? Use YYYY-MM-DD.",
    ResponseKey.INVALID_FULL_NAME: "That full name looks invalid. Please enter your first and last name.",
    ResponseKey.INVALID_PHONE: "That phone number looks invalid. Please enter at least 10 digits.",
    ResponseKey.INVALID_DOB: "That date of birth looks invalid. Please use YYYY-MM-DD.",
    ResponseKey.VERIFICATION_FAILED: "I couldn't verify your identity because the provided name, phone number, and date of birth do not match our records. Let's try again. What is your full name?",
    ResponseKey.VERIFICATION_LOCKED: "I couldn't verify your identity. For your security, this session is now locked. Please start a new session to try again.",
    ResponseKey.HELP_VERIFIED: "I'm CAPY. You are verified. You can ask me to list your appointments, confirm one, or cancel one.",
    ResponseKey.HELP_UNVERIFIED: "I'm CAPY. I need to verify your identity first. Please tell me your full name.",
    ResponseKey.CONFIRM_NOT_ALLOWED: "I couldn't confirm that appointment. Please choose a scheduled appointment.",
    ResponseKey.CANCEL_NOT_ALLOWED: "I couldn't cancel that appointment. Please choose a scheduled or confirmed appointment.",
    ResponseKey.APPOINTMENT_NOT_OWNED: "I couldn't complete that request. Please choose one of your appointments.",
    ResponseKey.APPOINTMENT_NOT_FOUND: "I couldn't find that appointment. Please ask to see your appointments first, then choose one by number or date.",
    ResponseKey.CONFIRM_MISSING_LIST_CONTEXT: "Please ask to see your appointments first, then tell me which one you want to confirm.",
    ResponseKey.CANCEL_MISSING_LIST_CONTEXT: "Please ask to see your appointments first, then tell me which one you want to cancel.",
    ResponseKey.CONFIRM_AMBIGUOUS_REFERENCE: "I couldn't tell which appointment you want to confirm. Please choose by number or date.",
    ResponseKey.CANCEL_AMBIGUOUS_REFERENCE: "I couldn't tell which appointment you want to cancel. Please choose by number or date.",
}


def build_response_text(state: ConversationState) -> str:
    response_key = state.turn.response_key
    if response_key is None:
        return "I couldn't complete that request right now. Please try again."
    if response_key == ResponseKey.APPOINTMENTS_LIST:
        if not state.appointments.listed_appointments:
            return "Thanks, you're verified. You do not have any appointments right now."
        lines = ["Thanks, you're verified. I am here to list, confirm, and cancel appointments. Here are your current appointments."]
        lines.extend(_appointment_lines(state))
        return "\n".join(lines)
    if response_key == ResponseKey.CONFIRM_SUCCESS:
        if state.turn.subject_appointment is None:
            return "I couldn't complete that request right now. Please try again."
        return _with_appointments_list("Confirmed. Here is your updated appointment list.", state)
    if response_key == ResponseKey.CONFIRM_ALREADY_CONFIRMED:
        if state.turn.subject_appointment is None:
            return "I couldn't complete that request right now. Please try again."
        return _with_appointments_list("That appointment was already confirmed. Here is your updated appointment list.", state)
    if response_key == ResponseKey.CANCEL_SUCCESS:
        if state.turn.subject_appointment is None:
            return "I couldn't complete that request right now. Please try again."
        return _with_appointments_list("Canceled. Here is your updated appointment list.", state)
    if response_key == ResponseKey.CANCEL_ALREADY_CANCELED:
        if state.turn.subject_appointment is None:
            return "I couldn't complete that request right now. Please try again."
        return _with_appointments_list("That appointment was already canceled. Here is your updated appointment list.", state)
    return STATIC_RESPONSES.get(response_key, "I couldn't complete that request right now. Please try again.")


def build_chat_response(thread_id: str, response_text: str, state: ConversationState) -> ChatTurnResponse:
    current_operation = state.turn.requested_operation
    if not state.verification.verified and current_operation in {
        ConversationOperation.UNKNOWN,
        ConversationOperation.HELP,
        ConversationOperation.VERIFY_IDENTITY,
    }:
        current_operation = ConversationOperation.VERIFY_IDENTITY

    appointments = None
    if (
        state.verification.verified
        and state.appointments.listed_appointments
        and current_operation in {
            ConversationOperation.LIST_APPOINTMENTS,
            ConversationOperation.CONFIRM_APPOINTMENT,
            ConversationOperation.CANCEL_APPOINTMENT,
        }
    ):
        appointments = [
            appointment.model_dump(include={"id", "date", "time", "doctor", "status"}, mode="json")
            for appointment in state.appointments.listed_appointments
        ]

    return ChatTurnResponse(
        response=response_text,
        verified=state.verification.verified,
        current_operation=current_operation,
        thread_id=thread_id,
        appointments=appointments,
        last_action_result=state.turn.operation_result,
        issue=state.turn.issue.value if state.turn.issue else None,
    )


def build_new_session_response(session) -> dict[str, str]:
    return {
        "session_id": session.session_id,
        "thread_id": session.thread_id,
        "response": "Hello, I'm CAPY. I can help you with your appointments.",
    }


def _with_appointments_list(text: str, state: ConversationState) -> str:
    if not state.appointments.listed_appointments:
        return text
    return f"{text}\n\n{_plain_appointments_list(state)}"


def _plain_appointments_list(state: ConversationState) -> str:
    return "\n".join(_appointment_lines(state))


def _appointment_lines(state: ConversationState) -> list[str]:
    return [
        f"{index}. {appointment.date} at {appointment.time} with {appointment.doctor} ({appointment.status.value})"
        for index, appointment in enumerate(state.appointments.listed_appointments, start=1)
    ]
