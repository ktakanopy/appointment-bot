from app.models import TurnIssue, VerificationStatus
from tests.support import build_test_workflow


def test_graph_locks_session_after_three_failed_verification_attempts():
    workflow = build_test_workflow()

    final = None
    for _ in range(3):
        workflow.run("graph-lock", "show my appointments")
        workflow.run("graph-lock", "Wrong Name")
        workflow.run("graph-lock", "11000000000")
        final = workflow.run("graph-lock", "1999-01-01")

    assert final is not None
    assert final.verification.verification_status == VerificationStatus.LOCKED
    assert final.turn.issue == TurnIssue.VERIFICATION_LOCKED
