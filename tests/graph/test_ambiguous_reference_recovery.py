from app.application.contracts.conversation import ConversationOperation, ConversationOperationOutcome, ConversationWorkflowInput
from app.llm.schemas import IntentPrediction, JudgeResult
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


class HistoryAwareProvider:
    name = "history-aware"

    def interpret(self, message, state):
        if message == "Ana Silva":
            return IntentPrediction(full_name="Ana Silva")
        if message == "11999998888":
            return IntentPrediction(phone="11999998888")
        if message == "1990-05-10":
            return IntentPrediction(dob="1990-05-10")
        if message == "confirm the first one":
            return IntentPrediction(
                requested_operation=ConversationOperation.CONFIRM_APPOINTMENT,
                appointment_reference="1",
            )
        if message == "cancel it":
            history = state.get("messages", [])
            if any(item.get("content") == "confirm the first one" for item in history):
                return IntentPrediction(
                    requested_operation=ConversationOperation.CANCEL_APPOINTMENT,
                    appointment_reference="1",
                )
        return IntentPrediction()

    def judge(self, scenario, transcript, observed_outcomes):
        return JudgeResult(status="pass", summary="ok", score=1.0)


def test_history_context_supports_follow_up_reference_resolution():
    workflow = build_test_workflow(provider=HistoryAwareProvider())

    for message in [
        "Ana Silva",
        "11999998888",
        "1990-05-10",
        "confirm the first one",
    ]:
        workflow.run(ConversationWorkflowInput(thread_id="graph-history-reference", incoming_message=message))

    result = workflow.run(
        ConversationWorkflowInput(thread_id="graph-history-reference", incoming_message="cancel it")
    )

    assert result.turn.issue is None
    assert result.turn.operation_result is not None
    assert result.turn.operation_result.outcome == ConversationOperationOutcome.CANCELED
