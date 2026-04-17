from app.models import ConversationOperation
from app.llm.schemas import IntentPrediction, JudgeResult
from app.responses import build_response_text
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


def test_verify_then_list_flow_lists_after_verification():
    workflow = build_test_workflow()

    first = workflow.run("graph-verify-list", "I want to see my appointments")
    second = workflow.run("graph-verify-list", "Ana Silva")
    third = workflow.run("graph-verify-list", "11999998888")
    final = workflow.run("graph-verify-list", "1990-05-10")

    assert first.turn.issue is None
    assert "full name" in build_response_text(first).lower()
    assert second.turn.issue is None
    assert "phone number" in build_response_text(second).lower()
    assert third.turn.issue is None
    assert "date of birth" in build_response_text(third).lower()
    assert final.verification.verified is True
    assert final.turn.requested_operation == ConversationOperation.LIST_APPOINTMENTS
    assert len(final.appointments.listed_appointments) == 2
    assert "current appointments" in build_response_text(final).lower()


def test_verify_then_list_ignores_operation_changes_during_identity_collection():
    workflow = build_test_workflow(provider=DeferredListProvider())

    workflow.run("graph-verify-stable-list", "I want to see my appointments")
    workflow.run("graph-verify-stable-list", "Ana Silva")
    workflow.run("graph-verify-stable-list", "11999998888")
    final = workflow.run("graph-verify-stable-list", "1990-05-10")

    assert final.verification.verified is True
    assert final.turn.requested_operation == ConversationOperation.LIST_APPOINTMENTS
    assert len(final.appointments.listed_appointments) == 2
    assert "current appointments" in build_response_text(final).lower()


def test_verify_without_prior_action_lists_appointments():
    workflow = build_test_workflow()

    workflow.run("graph-auto-list", "Ana Silva")
    workflow.run("graph-auto-list", "11999998888")
    final = workflow.run("graph-auto-list", "1990-05-10")

    assert final.verification.verified is True
    assert final.turn.requested_operation == ConversationOperation.LIST_APPOINTMENTS
    assert len(final.appointments.listed_appointments) == 2
    assert "current appointments" in build_response_text(final).lower()


def test_greeting_routes_into_verification_before_help():
    workflow = build_test_workflow()

    result = workflow.run("graph-greeting-verify", "hello")

    assert result.turn.requested_operation == ConversationOperation.VERIFY_IDENTITY
    assert "full name" in build_response_text(result).lower()
