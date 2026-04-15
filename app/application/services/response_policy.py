from __future__ import annotations

from collections.abc import Callable

from app.application.contracts.conversation import ConversationWorkflowResult, ResponseKey


class ResponsePolicy:
    def __init__(self):
        self._builders: dict[ResponseKey, Callable[[ConversationWorkflowResult], str]] = {
            ResponseKey.COLLECT_FULL_NAME: self._collect_full_name,
            ResponseKey.COLLECT_PHONE: self._collect_phone,
            ResponseKey.COLLECT_DOB: self._collect_dob,
            ResponseKey.INVALID_FULL_NAME: self._invalid_full_name,
            ResponseKey.INVALID_PHONE: self._invalid_phone,
            ResponseKey.INVALID_DOB: self._invalid_dob,
            ResponseKey.VERIFICATION_FAILED: self._verification_failed,
            ResponseKey.VERIFICATION_LOCKED: self._verification_locked,
            ResponseKey.HELP_VERIFIED: self._help_verified,
            ResponseKey.HELP_UNVERIFIED: self._help_unverified,
            ResponseKey.APPOINTMENTS_LIST: self._appointments_list,
            ResponseKey.CONFIRM_SUCCESS: self._confirm_success,
            ResponseKey.CONFIRM_ALREADY_CONFIRMED: self._confirm_already_confirmed,
            ResponseKey.CONFIRM_NOT_ALLOWED: self._confirm_not_allowed,
            ResponseKey.CANCEL_SUCCESS: self._cancel_success,
            ResponseKey.CANCEL_ALREADY_CANCELED: self._cancel_already_canceled,
            ResponseKey.CANCEL_NOT_ALLOWED: self._cancel_not_allowed,
            ResponseKey.APPOINTMENT_NOT_OWNED: self._appointment_not_owned,
            ResponseKey.APPOINTMENT_NOT_FOUND: self._appointment_not_found,
            ResponseKey.CONFIRM_MISSING_LIST_CONTEXT: self._confirm_missing_list_context,
            ResponseKey.CANCEL_MISSING_LIST_CONTEXT: self._cancel_missing_list_context,
            ResponseKey.CONFIRM_AMBIGUOUS_REFERENCE: self._confirm_ambiguous_reference,
            ResponseKey.CANCEL_AMBIGUOUS_REFERENCE: self._cancel_ambiguous_reference,
        }

    def build_fallback_text(self, workflow_result: ConversationWorkflowResult) -> str:
        response_key = workflow_result.turn.response_key
        if response_key is None:
            return self._default(workflow_result)
        builder = self._builders.get(response_key, self._default)
        return builder(workflow_result)

    def covered_response_keys(self) -> set[ResponseKey]:
        return set(self._builders)

    def _collect_full_name(self, workflow_result: ConversationWorkflowResult) -> str:
        return "I'm CAPY. I can help with that, but first I need to verify your identity. What is your full name?"

    def _collect_phone(self, workflow_result: ConversationWorkflowResult) -> str:
        return "Thanks. What phone number is on your clinic record?"

    def _collect_dob(self, workflow_result: ConversationWorkflowResult) -> str:
        return "Thanks. What is your date of birth? Use YYYY-MM-DD."

    def _invalid_full_name(self, workflow_result: ConversationWorkflowResult) -> str:
        return "That full name looks invalid. Please enter your first and last name."

    def _invalid_phone(self, workflow_result: ConversationWorkflowResult) -> str:
        return "That phone number looks invalid. Please enter at least 10 digits."

    def _invalid_dob(self, workflow_result: ConversationWorkflowResult) -> str:
        return "That date of birth looks invalid. Please use YYYY-MM-DD."

    def _verification_failed(self, workflow_result: ConversationWorkflowResult) -> str:
        return "I couldn't verify your identity because the provided name, phone number, and date of birth do not match our records. Let's try again. What is your full name?"

    def _verification_locked(self, workflow_result: ConversationWorkflowResult) -> str:
        return "I couldn't verify your identity. For your security, this session is now locked. Please start a new session to try again."

    def _help_verified(self, workflow_result: ConversationWorkflowResult) -> str:
        return "I'm CAPY. You are verified. You can ask me to list your appointments, confirm one, or cancel one."

    def _help_unverified(self, workflow_result: ConversationWorkflowResult) -> str:
        return "I'm CAPY. I need to verify your identity first. Please tell me your full name."

    def _appointments_list(self, workflow_result: ConversationWorkflowResult) -> str:
        if not workflow_result.listed_appointments:
            return "Thanks, you're verified. You do not have any appointments right now."
        lines = ["Thanks, you're verified. Here are your appointments. Would you like to confirm or cancel any of them?"]
        for index, appointment in enumerate(workflow_result.listed_appointments, start=1):
            lines.append(f"{index}. {appointment.date} at {appointment.time} with {appointment.doctor} ({appointment.status})")
        return "\n".join(lines)

    def _confirm_success(self, workflow_result: ConversationWorkflowResult) -> str:
        subject = workflow_result.turn.subject_appointment
        if subject is None:
            return self._default(workflow_result)
        return self._with_appointments_list(
            "Confirmed. Here is your updated appointment list.",
            workflow_result,
        )

    def _confirm_already_confirmed(self, workflow_result: ConversationWorkflowResult) -> str:
        subject = workflow_result.turn.subject_appointment
        if subject is None:
            return self._default(workflow_result)
        return self._with_appointments_list(
            "That appointment was already confirmed. Here is your updated appointment list.",
            workflow_result,
        )

    def _confirm_not_allowed(self, workflow_result: ConversationWorkflowResult) -> str:
        return "I couldn't confirm that appointment. Please choose a scheduled appointment."

    def _cancel_success(self, workflow_result: ConversationWorkflowResult) -> str:
        subject = workflow_result.turn.subject_appointment
        if subject is None:
            return self._default(workflow_result)
        return self._with_appointments_list(
            "Canceled. Here is your updated appointment list.",
            workflow_result,
        )

    def _cancel_already_canceled(self, workflow_result: ConversationWorkflowResult) -> str:
        subject = workflow_result.turn.subject_appointment
        if subject is None:
            return self._default(workflow_result)
        return self._with_appointments_list(
            "That appointment was already canceled. Here is your updated appointment list.",
            workflow_result,
        )

    def _cancel_not_allowed(self, workflow_result: ConversationWorkflowResult) -> str:
        return "I couldn't cancel that appointment. Please choose a scheduled or confirmed appointment."

    def _appointment_not_owned(self, workflow_result: ConversationWorkflowResult) -> str:
        return "I couldn't complete that request. Please choose one of your appointments."

    def _appointment_not_found(self, workflow_result: ConversationWorkflowResult) -> str:
        return "I couldn't find that appointment. Please ask to see your appointments first, then choose one by number or date."

    def _confirm_missing_list_context(self, workflow_result: ConversationWorkflowResult) -> str:
        return "Please ask to see your appointments first, then tell me which one you want to confirm."

    def _cancel_missing_list_context(self, workflow_result: ConversationWorkflowResult) -> str:
        return "Please ask to see your appointments first, then tell me which one you want to cancel."

    def _confirm_ambiguous_reference(self, workflow_result: ConversationWorkflowResult) -> str:
        return "I couldn't tell which appointment you want to confirm. Please choose by number or date."

    def _cancel_ambiguous_reference(self, workflow_result: ConversationWorkflowResult) -> str:
        return "I couldn't tell which appointment you want to cancel. Please choose by number or date."

    def _with_appointments_list(self, text: str, workflow_result: ConversationWorkflowResult) -> str:
        if not workflow_result.listed_appointments:
            return text
        return f"{text}\n\n{self._plain_appointments_list(workflow_result)}"

    def _plain_appointments_list(self, workflow_result: ConversationWorkflowResult) -> str:
        lines = []
        for index, appointment in enumerate(workflow_result.listed_appointments, start=1):
            lines.append(f"{index}. {appointment.date} at {appointment.time} with {appointment.doctor} ({appointment.status})")
        return "\n".join(lines)

    def _default(self, workflow_result: ConversationWorkflowResult) -> str:
        return "I couldn't complete that request right now. Please try again."
