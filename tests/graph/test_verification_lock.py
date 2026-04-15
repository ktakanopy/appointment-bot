from app.application.contracts.conversation import ConversationWorkflowInput, TurnIssue, VerificationStatus
from tests.support import build_test_workflow


def test_graph_locks_session_after_three_failed_verification_attempts():
    workflow = build_test_workflow()

    final = None
    for _ in range(3):
        workflow.run(ConversationWorkflowInput(thread_id="graph-lock", incoming_message="show my appointments"))
        workflow.run(ConversationWorkflowInput(thread_id="graph-lock", incoming_message="Wrong Name"))
        workflow.run(ConversationWorkflowInput(thread_id="graph-lock", incoming_message="11000000000"))
        final = workflow.run(ConversationWorkflowInput(thread_id="graph-lock", incoming_message="1999-01-01"))

    assert final is not None
    assert final.verification.status == VerificationStatus.LOCKED
    assert final.turn.issue == TurnIssue.VERIFICATION_LOCKED
