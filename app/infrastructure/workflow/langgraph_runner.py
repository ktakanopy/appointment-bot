from __future__ import annotations

from typing import Any

from app.application.contracts.conversation import (
    ConversationWorkflowInput,
    ConversationWorkflowResult,
    TurnSnapshot,
    VerificationSnapshot,
    VerificationStatus,
)
from app.graph.state import ConversationState
from app.observability import record_trace_event


class LangGraphConversationWorkflow:
    def __init__(self, graph, logger, tracer=None):
        self.graph = graph
        self.logger = logger
        self.tracer = tracer

    def run(self, workflow_input: ConversationWorkflowInput) -> ConversationWorkflowResult:
        payload = self._payload(workflow_input)
        config = {"configurable": {"thread_id": workflow_input.thread_id}}
        record_trace_event(
            self.logger,
            self.tracer,
            "workflow.start",
            {"thread_id": workflow_input.thread_id, "payload": payload},
        )
        result = self.graph.invoke(payload, config)
        record_trace_event(
            self.logger,
            self.tracer,
            "workflow.end",
            {"thread_id": workflow_input.thread_id, "result": result},
        )
        state = ConversationState.model_validate(result)
        return ConversationWorkflowResult(
            thread_id=state.thread_id,
            verification=VerificationSnapshot(
                verified=state.verification.verified,
                status=state.verification.verification_status,
                failures=state.verification.verification_failures,
                patient_id=state.verification.patient_id,
                provided_full_name=state.verification.provided_full_name,
                provided_phone=state.verification.provided_phone,
                provided_dob=state.verification.provided_dob,
            ),
            turn=TurnSnapshot(
                requested_operation=state.turn.requested_operation,
                deferred_operation=state.turn.deferred_operation,
                response_key=state.turn.response_key,
                issue=state.turn.issue,
                operation_result=state.turn.operation_result,
                subject_appointment=state.turn.subject_appointment,
            ),
            listed_appointments=list(state.appointments.listed_appointments),
            appointment_reference=state.appointments.appointment_reference,
        )

    def _payload(self, workflow_input: ConversationWorkflowInput) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "thread_id": workflow_input.thread_id,
            "incoming_message": workflow_input.incoming_message,
        }
        if workflow_input.bootstrap_verification is not None:
            payload["verification"] = {
                "verified": workflow_input.bootstrap_verification.verified,
                "verification_status": VerificationStatus.VERIFIED.value,
                "patient_id": workflow_input.bootstrap_verification.patient_id,
            }
        return payload
