from app.application.contracts.conversation import (
    ConversationOperation,
    ConversationWorkflowInput,
    ResponseKey,
)
from app.llm.schemas import IntentPrediction, JudgeResult
from tests.support import build_test_workflow


class DeferredListProvider:
    name = "test"

    def interpret(self, message, state):
        if message == "I want to see my appointments":
            return IntentPrediction(requested_operation=ConversationOperation.LIST_APPOINTMENTS)
        if message == "Ana Silva":
            return IntentPrediction(
                requested_operation=ConversationOperation.CONFIRM_APPOINTMENT,
                full_name="Ana Silva",
            )
        if message == "11999998888":
            return IntentPrediction(
                requested_operation=ConversationOperation.CANCEL_APPOINTMENT,
                phone="11999998888",
            )
        if message == "1990-05-10":
            return IntentPrediction(
                requested_operation=ConversationOperation.CONFIRM_APPOINTMENT,
                dob="1990-05-10",
            )
        return IntentPrediction()

    def judge(self, scenario, transcript, observed_outcomes):
        return JudgeResult(status="pass", summary="Test judge completed.", score=1.0)


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


def test_verify_then_list_keeps_original_deferred_action_during_identity_collection():
    workflow = build_test_workflow(provider=DeferredListProvider())

    workflow.run(ConversationWorkflowInput(thread_id="graph-verify-stable-list", incoming_message="I want to see my appointments"))
    workflow.run(ConversationWorkflowInput(thread_id="graph-verify-stable-list", incoming_message="Ana Silva"))
    workflow.run(ConversationWorkflowInput(thread_id="graph-verify-stable-list", incoming_message="11999998888"))
    final = workflow.run(ConversationWorkflowInput(thread_id="graph-verify-stable-list", incoming_message="1990-05-10"))

    assert final.verification.verified is True
    assert final.turn.requested_operation == ConversationOperation.LIST_APPOINTMENTS
    assert final.turn.response_key == ResponseKey.APPOINTMENTS_LIST
    assert len(final.listed_appointments) == 2


def test_greeting_routes_into_verification_before_help():
    workflow = build_test_workflow()

    result = workflow.run(ConversationWorkflowInput(thread_id="graph-greeting-verify", incoming_message="hello"))

    assert result.turn.requested_operation == ConversationOperation.VERIFY_IDENTITY
    assert result.turn.response_key == ResponseKey.COLLECT_FULL_NAME
