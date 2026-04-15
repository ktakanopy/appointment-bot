from app.application.contracts.conversation import (
    ConversationOperation,
    ConversationOperationOutcome,
    ConversationWorkflowInput,
)
from tests.support import build_test_workflow


def test_cancel_then_reroute_back_to_list():
    workflow = build_test_workflow()

    for message in [
        "show me my appointments",
        "Ana Silva",
        "11999998888",
        "1990-05-10",
    ]:
        workflow.run(ConversationWorkflowInput(thread_id="graph-cancel", incoming_message=message))

    canceled = workflow.run(ConversationWorkflowInput(thread_id="graph-cancel", incoming_message="cancel the first one"))
    refreshed = workflow.run(
        ConversationWorkflowInput(thread_id="graph-cancel", incoming_message="show me my appointments again")
    )

    assert canceled.turn.operation_result.outcome == ConversationOperationOutcome.CANCELED
    assert canceled.listed_appointments[0].status == "canceled"
    assert refreshed.turn.requested_operation == ConversationOperation.LIST_APPOINTMENTS
    assert refreshed.listed_appointments[0].status == "canceled"
