from __future__ import annotations

from app.application.contracts.conversation import (
    ConversationOperation,
    ConversationWorkflowResult,
)
from app.application.contracts.public import AppointmentSummary, ChatTurnResponse, RememberedIdentitySummary


class ChatPresenter:
    def present(
        self,
        *,
        thread_id: str,
        response_text: str,
        workflow_result: ConversationWorkflowResult,
        remembered_identity_status: RememberedIdentitySummary,
    ) -> ChatTurnResponse:
        current_operation = workflow_result.turn.requested_operation
        if not workflow_result.verification.verified and current_operation in {
            ConversationOperation.UNKNOWN,
            ConversationOperation.HELP,
            ConversationOperation.VERIFY_IDENTITY,
        }:
            current_operation = ConversationOperation.VERIFY_IDENTITY
        appointments = None
        if (
            workflow_result.verification.verified
            and workflow_result.listed_appointments
            and current_operation in {
                ConversationOperation.LIST_APPOINTMENTS,
                ConversationOperation.CONFIRM_APPOINTMENT,
                ConversationOperation.CANCEL_APPOINTMENT,
            }
        ):
            appointments = [
                AppointmentSummary(
                    id=appointment.id,
                    date=appointment.date,
                    time=appointment.time,
                    doctor=appointment.doctor,
                    status=appointment.status,
                )
                for appointment in workflow_result.listed_appointments
            ]
        return ChatTurnResponse(
            response=response_text,
            verified=workflow_result.verification.verified,
            current_operation=current_operation,
            thread_id=thread_id,
            appointments=appointments,
            last_action_result=workflow_result.turn.operation_result,
            issue=workflow_result.turn.issue.value if workflow_result.turn.issue else None,
            remembered_identity_status=remembered_identity_status,
        )
