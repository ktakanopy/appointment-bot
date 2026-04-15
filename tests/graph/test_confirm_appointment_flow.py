from app.models import ActionOutcome
from tests.support import build_test_workflow


def test_confirm_flow_resolves_first_appointment_and_is_idempotent():
    workflow = build_test_workflow()

    for message in [
        "show me my appointments",
        "Ana Silva",
        "11999998888",
        "1990-05-10",
    ]:
        workflow.run("graph-confirm", message)

    confirmed = workflow.run("graph-confirm", "confirm the first one")
    confirmed_again = workflow.run("graph-confirm", "confirm the first one")

    assert confirmed.turn.operation_result.outcome == ActionOutcome.CONFIRMED
    assert confirmed_again.turn.operation_result.outcome == ActionOutcome.ALREADY_CONFIRMED
    assert confirmed.appointments.listed_appointments[0].status == "confirmed"
    assert confirmed_again.appointments.listed_appointments[0].status == "confirmed"


def test_confirm_flow_resolves_date_reference_after_listing():
    workflow = build_test_workflow()

    for message in [
        "show me my appointments, I'm Ana Silva",
        "11999998888",
        "1990-05-10",
    ]:
        workflow.run("graph-confirm-date", message)

    confirmed = workflow.run("graph-confirm-date", "confirm my 2026-04-20 appointment")

    assert confirmed.turn.operation_result.outcome == ActionOutcome.CONFIRMED
    assert confirmed.appointments.listed_appointments[0].status == "confirmed"
