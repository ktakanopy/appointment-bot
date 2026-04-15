from __future__ import annotations

from app.application.contracts.conversation import (
    ConversationOperation,
    ConversationWorkflowResult,
    ResponseKey,
)
from app.application.contracts.public import AppointmentSummary, ChatTurnResponse, RememberedIdentitySummary
from app.llm.base import LLMProvider


class ChatPresenter:
    def __init__(self, provider: LLMProvider):
        self.provider = provider

    def present(
        self,
        *,
        thread_id: str,
        workflow_result: ConversationWorkflowResult,
        remembered_identity_status: RememberedIdentitySummary,
    ) -> ChatTurnResponse:
        fallback_text = self._fallback_text(workflow_result)
        response = self.provider.generate_response(
            self._provider_state(workflow_result),
            fallback_text,
        )
        current_operation = workflow_result.turn.requested_operation
        if not workflow_result.verification.verified and current_operation in {
            ConversationOperation.UNKNOWN,
            ConversationOperation.HELP,
            ConversationOperation.VERIFY_IDENTITY,
        }:
            current_operation = ConversationOperation.VERIFY_IDENTITY
        appointments = None
        if current_operation == ConversationOperation.LIST_APPOINTMENTS and workflow_result.listed_appointments:
            appointments = [
                AppointmentSummary(
                    id=appointment.id,
                    date=appointment.date,
                    time=appointment.time,
                    doctor=appointment.doctor,
                    status=appointment.status.value,
                )
                for appointment in workflow_result.listed_appointments
            ]
        return ChatTurnResponse(
            response=response.response_text,
            verified=workflow_result.verification.verified,
            current_operation=current_operation,
            thread_id=thread_id,
            appointments=appointments,
            last_action_result=workflow_result.turn.operation_result,
            issue=workflow_result.turn.issue.value if workflow_result.turn.issue else None,
            remembered_identity_status=remembered_identity_status,
        )

    def _provider_state(self, workflow_result: ConversationWorkflowResult) -> dict[str, object]:
        return {
            "verification": workflow_result.verification.model_dump(mode="json"),
            "turn": workflow_result.turn.model_dump(mode="json"),
            "listed_appointments": [appointment.model_dump(mode="json") for appointment in workflow_result.listed_appointments],
        }

    def _fallback_text(self, workflow_result: ConversationWorkflowResult) -> str:
        response_key = workflow_result.turn.response_key
        subject = workflow_result.turn.subject_appointment
        if response_key == ResponseKey.COLLECT_FULL_NAME:
            return "I'm CAPY. I can help with that, but first I need to verify your identity. What is your full name?"
        if response_key == ResponseKey.COLLECT_PHONE:
            return "Thanks. What phone number is on your clinic record?"
        if response_key == ResponseKey.COLLECT_DOB:
            return "Thanks. What is your date of birth? Use YYYY-MM-DD."
        if response_key == ResponseKey.INVALID_FULL_NAME:
            return "That full name looks invalid. Please enter your first and last name."
        if response_key == ResponseKey.INVALID_PHONE:
            return "That phone number looks invalid. Please enter at least 10 digits."
        if response_key == ResponseKey.INVALID_DOB:
            return "That date of birth looks invalid. Please use YYYY-MM-DD."
        if response_key == ResponseKey.VERIFICATION_FAILED:
            return "I couldn't verify your identity because the provided name, phone number, and date of birth do not match our records. Let's try again. What is your full name?"
        if response_key == ResponseKey.VERIFICATION_LOCKED:
            return "I couldn't verify your identity. For your security, this session is now locked. Please start a new session to try again."
        if response_key == ResponseKey.HELP_VERIFIED:
            return "I'm CAPY. You are verified. You can ask me to list your appointments, confirm one, or cancel one."
        if response_key == ResponseKey.HELP_UNVERIFIED:
            return "I'm CAPY. I need to verify your identity first. Please tell me your full name."
        if response_key == ResponseKey.APPOINTMENTS_LIST:
            if not workflow_result.listed_appointments:
                return "You do not have any appointments right now."
            lines = ["Here are your appointments:"]
            for index, appointment in enumerate(workflow_result.listed_appointments, start=1):
                lines.append(
                    f"{index}. {appointment.date} at {appointment.time} with {appointment.doctor} ({appointment.status.value})"
                )
            return "\n".join(lines)
        if response_key == ResponseKey.CONFIRM_SUCCESS and subject is not None:
            return f"Your appointment for {subject.date} at {subject.time} is now confirmed."
        if response_key == ResponseKey.CONFIRM_ALREADY_CONFIRMED and subject is not None:
            return f"That appointment was already confirmed for {subject.date} at {subject.time}."
        if response_key == ResponseKey.CONFIRM_NOT_ALLOWED:
            return "I couldn't confirm that appointment. Please choose a scheduled appointment."
        if response_key == ResponseKey.CANCEL_SUCCESS and subject is not None:
            return f"Your appointment for {subject.date} at {subject.time} has been canceled."
        if response_key == ResponseKey.CANCEL_ALREADY_CANCELED and subject is not None:
            return f"That appointment was already canceled for {subject.date} at {subject.time}."
        if response_key == ResponseKey.CANCEL_NOT_ALLOWED:
            return "I couldn't cancel that appointment. Please choose a scheduled or confirmed appointment."
        if response_key == ResponseKey.APPOINTMENT_NOT_OWNED:
            return "I couldn't complete that request. Please choose one of your appointments."
        if response_key == ResponseKey.APPOINTMENT_NOT_FOUND:
            return "I couldn't find that appointment. Please ask to see your appointments first, then choose one by number or date."
        if response_key == ResponseKey.CONFIRM_MISSING_LIST_CONTEXT:
            return "Please ask to see your appointments first, then tell me which one you want to confirm."
        if response_key == ResponseKey.CANCEL_MISSING_LIST_CONTEXT:
            return "Please ask to see your appointments first, then tell me which one you want to cancel."
        if response_key == ResponseKey.CONFIRM_AMBIGUOUS_REFERENCE:
            return "I couldn't tell which appointment you want to confirm. Please choose by number or date."
        if response_key == ResponseKey.CANCEL_AMBIGUOUS_REFERENCE:
            return "I couldn't tell which appointment you want to cancel. Please choose by number or date."
        return "I couldn't complete that request right now. Please try again."
