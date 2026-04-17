import pytest

from app.graph.state import ConversationState, VerificationState
from app.models import ActionOutcome, Appointment, AppointmentStatus, ConversationOperation, ConversationOperationResult, TurnIssue
from app.responses import build_response_text


def test_missing_verification_fields_tracks_unset_values():
    verification = VerificationState(
        provided_full_name="Ana Silva",
        provided_phone=None,
        provided_dob=None,
    )

    assert verification.missing_fields() == ["phone", "dob"]


def test_action_and_appointment_rules_cover_status_and_ownership():
    scheduled = Appointment(
        id="a1",
        patient_id="p1",
        date="2026-04-20",
        time="14:00",
        doctor="Dr. Costa",
        status=AppointmentStatus.SCHEDULED,
    )
    confirmed = Appointment(
        id="a2",
        patient_id="p1",
        date="2026-04-23",
        time="09:30",
        doctor="Dr. Lima",
        status=AppointmentStatus.CONFIRMED,
    )
    canceled = Appointment(
        id="a3",
        patient_id="p1",
        date="2026-04-25",
        time="11:00",
        doctor="Dr. Lima",
        status=AppointmentStatus.CANCELED,
    )

    assert ConversationOperation.LIST_APPOINTMENTS.requires_verification is True
    assert ConversationOperation.HELP.requires_verification is False
    assert scheduled.is_confirmable is True
    assert confirmed.is_confirmable is False
    assert confirmed.is_cancelable is True
    assert canceled.is_cancelable is False
    assert scheduled.is_owned_by("p1") is True
    assert scheduled.is_owned_by("p2") is False


@pytest.mark.parametrize(
    ("issue", "operation_result", "requested_operation", "expected_text"),
    [
        (TurnIssue.INVALID_FULL_NAME, None, ConversationOperation.VERIFY_IDENTITY, "first and last name"),
        (TurnIssue.INVALID_PHONE, None, ConversationOperation.VERIFY_IDENTITY, "at least 10 digits"),
        (TurnIssue.INVALID_DOB, None, ConversationOperation.VERIFY_IDENTITY, "YYYY-MM-DD"),
        (TurnIssue.INVALID_IDENTITY, None, ConversationOperation.VERIFY_IDENTITY, "do not match our records"),
        (TurnIssue.VERIFICATION_LOCKED, None, ConversationOperation.VERIFY_IDENTITY, "session is now locked"),
        (TurnIssue.APPOINTMENT_NOT_CONFIRMABLE, None, ConversationOperation.CONFIRM_APPOINTMENT, "scheduled appointment"),
        (TurnIssue.APPOINTMENT_NOT_CANCELABLE, None, ConversationOperation.CANCEL_APPOINTMENT, "scheduled or confirmed"),
        (TurnIssue.APPOINTMENT_NOT_OWNED, None, ConversationOperation.CONFIRM_APPOINTMENT, "one of your appointments"),
        (TurnIssue.APPOINTMENT_NOT_FOUND, None, ConversationOperation.CONFIRM_APPOINTMENT, "choose one by number or date"),
        (TurnIssue.MISSING_LIST_CONTEXT, None, ConversationOperation.CONFIRM_APPOINTMENT, "see your appointments first"),
        (TurnIssue.AMBIGUOUS_APPOINTMENT_REFERENCE, None, ConversationOperation.CANCEL_APPOINTMENT, "choose by number or date"),
        (None, ConversationOperationResult(operation=ConversationOperation.CONFIRM_APPOINTMENT, outcome=ActionOutcome.CONFIRMED, appointment_id="a1"), ConversationOperation.CONFIRM_APPOINTMENT, "Confirmed. Here is your updated appointment list."),
        (None, ConversationOperationResult(operation=ConversationOperation.CANCEL_APPOINTMENT, outcome=ActionOutcome.CANCELED, appointment_id="a1"), ConversationOperation.CANCEL_APPOINTMENT, "Canceled. Here is your updated appointment list."),
        (None, ConversationOperationResult(operation=ConversationOperation.CONFIRM_APPOINTMENT, outcome=ActionOutcome.ALREADY_CONFIRMED, appointment_id="a1"), ConversationOperation.CONFIRM_APPOINTMENT, "already confirmed"),
        (None, ConversationOperationResult(operation=ConversationOperation.CANCEL_APPOINTMENT, outcome=ActionOutcome.ALREADY_CANCELED, appointment_id="a1"), ConversationOperation.CANCEL_APPOINTMENT, "already canceled"),
    ],
)
def test_build_response_text_returns_text_for_supported_turn_outcomes(issue, operation_result, requested_operation, expected_text):
    state = ConversationState(thread_id="thread-1")
    state.turn.issue = issue
    state.turn.operation_result = operation_result
    state.turn.requested_operation = requested_operation
    state.verification.verified = requested_operation != ConversationOperation.VERIFY_IDENTITY
    state.appointments.listed_appointments = [
        Appointment(
            id="a1",
            patient_id="p1",
            date="2026-04-20",
            time="14:00",
            doctor="Dr. Costa",
            status=AppointmentStatus.SCHEDULED,
        )
    ]

    assert expected_text in build_response_text(state)


def test_build_response_text_prompts_for_next_missing_verification_field():
    state = ConversationState(thread_id="thread-1")
    state.turn.requested_operation = ConversationOperation.VERIFY_IDENTITY

    assert "full name" in build_response_text(state).lower()

    state.verification.provided_full_name = "Ana Silva"
    assert "phone number" in build_response_text(state).lower()

    state.verification.provided_phone = "11999998888"
    assert "date of birth" in build_response_text(state).lower()


def test_build_response_text_lists_appointments_for_verified_user():
    state = ConversationState(thread_id="thread-1")
    state.verification.verified = True
    state.turn.requested_operation = ConversationOperation.LIST_APPOINTMENTS
    state.turn.operation_result = ConversationOperationResult(
        operation=ConversationOperation.LIST_APPOINTMENTS,
        outcome=ActionOutcome.LISTED,
    )
    state.appointments.listed_appointments = [
        Appointment(
            id="a1",
            patient_id="p1",
            date="2026-04-20",
            time="14:00",
            doctor="Dr. Costa",
            status=AppointmentStatus.SCHEDULED,
        )
    ]

    text = build_response_text(state)
    assert "current appointments" in text.lower()
    assert "1. 2026-04-20 at 14:00" in text
