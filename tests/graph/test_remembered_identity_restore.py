from __future__ import annotations

from app.application.contracts.conversation import (
    ConversationOperation,
    ConversationWorkflowInput,
    WorkflowVerificationBootstrap,
)
from tests.support import build_test_workflow


def test_graph_allows_list_action_when_session_bootstraps_verified_patient():
    workflow = build_test_workflow()

    result = workflow.run(
        ConversationWorkflowInput(
            thread_id="graph-remembered-restore",
            incoming_message="show my appointments",
            bootstrap_verification=WorkflowVerificationBootstrap(patient_id="p1"),
        )
    )

    assert result.verification.verified is True
    assert result.turn.requested_operation == ConversationOperation.LIST_APPOINTMENTS
    assert len(result.listed_appointments) == 2
