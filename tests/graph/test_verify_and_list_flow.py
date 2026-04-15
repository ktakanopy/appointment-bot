from app.application.contracts.conversation import (
    ConversationOperation,
    ConversationWorkflowInput,
    ResponseKey,
)
from tests.support import build_test_workflow


def test_verify_then_list_flow_resumes_deferred_action():
    workflow = build_test_workflow()

    first = workflow.run(ConversationWorkflowInput(thread_id="graph-verify-list", incoming_message="I want to see my appointments"))
    second = workflow.run(ConversationWorkflowInput(thread_id="graph-verify-list", incoming_message="Ana Silva"))
    third = workflow.run(ConversationWorkflowInput(thread_id="graph-verify-list", incoming_message="11999998888"))
    final = workflow.run(ConversationWorkflowInput(thread_id="graph-verify-list", incoming_message="1990-05-10"))

    assert first.turn.response_key == ResponseKey.COLLECT_FULL_NAME
    assert second.turn.response_key == ResponseKey.COLLECT_PHONE
    assert third.turn.response_key == ResponseKey.COLLECT_DOB
    assert final.verification.verified is True
    assert final.turn.requested_operation == ConversationOperation.LIST_APPOINTMENTS
    assert len(final.listed_appointments) == 2
    assert final.turn.response_key == ResponseKey.APPOINTMENTS_LIST


def test_greeting_routes_into_verification_before_help():
    workflow = build_test_workflow()

    result = workflow.run(ConversationWorkflowInput(thread_id="graph-greeting-verify", incoming_message="hello"))

    assert result.turn.requested_operation == ConversationOperation.VERIFY_IDENTITY
    assert result.turn.response_key == ResponseKey.COLLECT_FULL_NAME
