from __future__ import annotations

from app.models import ConversationOperation, ConversationWorkflowInput, ResponseKey
from tests.support import build_test_workflow


def test_in_memory_checkpointer_preserves_thread_state_within_runtime():
    workflow = build_test_workflow()

    workflow.run(ConversationWorkflowInput(thread_id="in-memory-thread", incoming_message="show my appointments"))
    workflow.run(ConversationWorkflowInput(thread_id="in-memory-thread", incoming_message="Ana Silva"))
    second_result = workflow.run(ConversationWorkflowInput(thread_id="in-memory-thread", incoming_message="11999998888"))
    final_result = workflow.run(ConversationWorkflowInput(thread_id="in-memory-thread", incoming_message="1990-05-10"))

    assert second_result.turn.response_key == ResponseKey.COLLECT_DOB
    assert final_result.verification.verified is True
    assert final_result.turn.requested_operation == ConversationOperation.LIST_APPOINTMENTS
    assert len(final_result.listed_appointments) == 2
