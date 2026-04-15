from app.models import ActionOutcome, ConversationOperation
from tests.support import build_test_workflow


def test_cancel_then_reroute_back_to_list():
    workflow = build_test_workflow()

    for message in [
        "show me my appointments",
        "Ana Silva",
        "11999998888",
        "1990-05-10",
    ]:
        workflow.run("graph-cancel", message)

    canceled = workflow.run("graph-cancel", "cancel the first one")
    refreshed = workflow.run("graph-cancel", "show me my appointments again")

    assert canceled.turn.operation_result.outcome == ActionOutcome.CANCELED
    assert canceled.appointments.listed_appointments[0].status == "canceled"
    assert refreshed.turn.requested_operation == ConversationOperation.LIST_APPOINTMENTS
    assert refreshed.appointments.listed_appointments[0].status == "canceled"


def test_cancel_second_reference_replaces_previous_selection():
    workflow = build_test_workflow()

    for message in [
        "show me my appointments",
        "Ana Silva",
        "11999998888",
        "1990-05-10",
    ]:
        workflow.run("graph-cancel-second", message)

    workflow.run("graph-cancel-second", "confirm the first one")
    canceled = workflow.run("graph-cancel-second", "cancel the second one")

    assert canceled.turn.operation_result.outcome == ActionOutcome.CANCELED
    assert canceled.turn.operation_result.appointment_id == "a2"
    assert canceled.appointments.listed_appointments[0].status == "confirmed"
    assert canceled.appointments.listed_appointments[1].status == "canceled"
