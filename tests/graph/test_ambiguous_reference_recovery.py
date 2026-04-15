from app.application.contracts.conversation import ConversationWorkflowInput, ResponseKey, TurnIssue
from tests.support import build_test_workflow


def test_confirm_ordinal_without_current_list_asks_for_list_first():
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

    assert result.turn.issue == TurnIssue.MISSING_LIST_CONTEXT
    assert result.turn.response_key == ResponseKey.CONFIRM_MISSING_LIST_CONTEXT
