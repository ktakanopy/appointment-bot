from app.application.contracts.conversation import ConversationOperationOutcome, ConversationWorkflowInput
from tests.support import build_test_workflow


def test_confirm_flow_resolves_first_appointment_and_is_idempotent():
    workflow = build_test_workflow()

    for message in [
        "show me my appointments",
        "Ana Silva",
        "11999998888",
        "1990-05-10",
    ]:
        workflow.run(ConversationWorkflowInput(thread_id="graph-confirm", incoming_message=message))

    confirmed = workflow.run(ConversationWorkflowInput(thread_id="graph-confirm", incoming_message="confirm the first one"))
    confirmed_again = workflow.run(
        ConversationWorkflowInput(thread_id="graph-confirm", incoming_message="confirm the first one")
    )

    assert confirmed.turn.operation_result.outcome == ConversationOperationOutcome.CONFIRMED
    assert confirmed_again.turn.operation_result.outcome == ConversationOperationOutcome.ALREADY_CONFIRMED
    assert confirmed.listed_appointments[0].status == "confirmed"
    assert confirmed_again.listed_appointments[0].status == "confirmed"


def test_confirm_flow_resolves_date_reference_after_listing():
    workflow = build_test_workflow()

    for message in [
        "show me my appointments, I'm Ana Silva",
        "11999998888",
        "1990-05-10",
    ]:
        workflow.run(ConversationWorkflowInput(thread_id="graph-confirm-date", incoming_message=message))

    confirmed = workflow.run(
        ConversationWorkflowInput(
            thread_id="graph-confirm-date",
            incoming_message="confirm my 2026-04-20 appointment",
        )
    )

    assert confirmed.turn.operation_result.outcome == ConversationOperationOutcome.CONFIRMED
    assert confirmed.listed_appointments[0].status == "confirmed"
