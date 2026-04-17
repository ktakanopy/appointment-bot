from __future__ import annotations

from app.graph.state import ConversationState
from app.models import (
    ActionOutcome,
    ChatTurnResponse,
    ConversationOperation,
    NewSessionResponseData,
    TurnIssue,
)


def build_response_text(state: ConversationState) -> str:
    issue = state.turn.issue
    if issue is not None:
        return _issue_response(state, issue)

    result = state.turn.operation_result
    if result is not None:
        if result.operation == ConversationOperation.LIST_APPOINTMENTS:
            return _appointments_list_response(state)
        if result.outcome == ActionOutcome.CONFIRMED:
            return _with_appointments_list("Confirmed. Here is your updated appointment list.", state)
        if result.outcome == ActionOutcome.ALREADY_CONFIRMED:
            return _with_appointments_list(
                "That appointment was already confirmed. Here is your updated appointment list.",
                state,
            )
        if result.outcome == ActionOutcome.CANCELED:
            return _with_appointments_list("Canceled. Here is your updated appointment list.", state)
        if result.outcome == ActionOutcome.ALREADY_CANCELED:
            return _with_appointments_list(
                "That appointment was already canceled. Here is your updated appointment list.",
                state,
            )

    if state.turn.requested_operation == ConversationOperation.LIST_APPOINTMENTS and state.verification.verified:
        return _appointments_list_response(state)

    if not state.verification.verified:
        return _verification_prompt(state)

    if state.turn.requested_operation in {
        ConversationOperation.HELP,
        ConversationOperation.UNKNOWN,
        ConversationOperation.VERIFY_IDENTITY,
    }:
        return "I'm CAPY. You are verified. You can ask me to list your appointments, confirm one, or cancel one."

    return "I couldn't complete that request right now. Please try again."


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


def build_new_session_response(session) -> NewSessionResponseData:
    return NewSessionResponseData(
        session_id=session.session_id,
        thread_id=session.thread_id,
        response="Hello, I'm CAPY. I can help you with your appointments.",
    )


def _appointments_list_response(state: ConversationState) -> str:
    if not state.appointments.listed_appointments:
        return "Thanks, you're verified. You do not have any appointments right now."
    lines = ["Thanks, you're verified. I am here to list, confirm, and cancel appointments. Here are your current appointments."]
    lines.extend(_appointment_lines(state))
    return "\n".join(lines)


def _issue_response(state: ConversationState, issue: TurnIssue) -> str:
    if issue == TurnIssue.INVALID_FULL_NAME:
        return "That full name looks invalid. Please enter your first and last name."
    if issue == TurnIssue.INVALID_PHONE:
        return "That phone number looks invalid. Please enter at least 10 digits."
    if issue == TurnIssue.INVALID_DOB:
        return "That date of birth looks invalid. Please use YYYY-MM-DD."
    if issue == TurnIssue.INVALID_IDENTITY:
        return "I couldn't verify your identity because the provided name, phone number, and date of birth do not match our records. Let's try again. What is your full name?"
    if issue == TurnIssue.VERIFICATION_LOCKED:
        return "I couldn't verify your identity. For your security, this session is now locked. Please start a new session to try again."
    if issue == TurnIssue.APPOINTMENT_NOT_CONFIRMABLE:
        return "I couldn't confirm that appointment. Please choose a scheduled appointment."
    if issue == TurnIssue.APPOINTMENT_NOT_CANCELABLE:
        return "I couldn't cancel that appointment. Please choose a scheduled or confirmed appointment."
    if issue == TurnIssue.APPOINTMENT_NOT_OWNED:
        return "I couldn't complete that request. Please choose one of your appointments."
    if issue == TurnIssue.APPOINTMENT_NOT_FOUND:
        return "I couldn't find that appointment. Please ask to see your appointments first, then choose one by number or date."
    if issue == TurnIssue.MISSING_LIST_CONTEXT:
        if state.turn.requested_operation == ConversationOperation.CONFIRM_APPOINTMENT:
            return "Please ask to see your appointments first, then tell me which one you want to confirm."
        return "Please ask to see your appointments first, then tell me which one you want to cancel."
    if issue == TurnIssue.AMBIGUOUS_APPOINTMENT_REFERENCE:
        if state.turn.requested_operation == ConversationOperation.CONFIRM_APPOINTMENT:
            return "I couldn't tell which appointment you want to confirm. Please choose by number or date."
        return "I couldn't tell which appointment you want to cancel. Please choose by number or date."
    return "I couldn't complete that request right now. Please try again."


def _verification_prompt(state: ConversationState) -> str:
    if state.turn.requested_operation == ConversationOperation.HELP:
        return "I'm CAPY. I need to verify your identity first. Please tell me your full name."

    missing = state.verification.missing_fields()
    if not missing:
        return "I'm CAPY. I need to verify your identity first. Please tell me your full name."

    next_field = missing[0]
    if next_field == "full_name":
        return "I'm CAPY. I can help you list, confirm, and cancel appointments, but first you need to identify yourself. What is your full name?"
    if next_field == "phone":
        return "Thanks. What phone number is on your clinic record?"
    return "Thanks. What is your date of birth? Use YYYY-MM-DD."


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
