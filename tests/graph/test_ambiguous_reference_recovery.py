from app.application.contracts.conversation import ConversationOperationOutcome, ConversationWorkflowInput
from tests.support import build_test_workflow


def test_confirm_ordinal_after_verification_uses_auto_list_context():
    workflow = build_test_workflow()

    for message in [
        "Ana Silva",
        "11999998888",
        "1990-05-10",
    ]:
        workflow.run(ConversationWorkflowInput(thread_id="graph-ambiguous", incoming_message=message))

    result = workflow.run(
        ConversationWorkflowInput(thread_id="graph-ambiguous", incoming_message="confirm the first one")
    )

    assert result.turn.issue is None
    assert result.turn.operation_result is not None
    assert result.turn.operation_result.outcome == ConversationOperationOutcome.CONFIRMED
