from app.application.contracts.conversation import ConversationOperation
from app.domain.models import Appointment, AppointmentStatus
from app.graph.state import VerificationState


def test_missing_verification_fields_tracks_unset_values():
    verification = VerificationState(
        provided_full_name="Ana Silva",
        provided_phone=None,
        provided_dob=None,
    )

    assert verification.missing_fields() == ["phone", "dob"]


def test_action_and_appointment_rules_cover_status_and_ownership():
    scheduled = Appointment("a1", "p1", "2026-04-20", "14:00", "Dr. Costa", AppointmentStatus.SCHEDULED)
    confirmed = Appointment("a2", "p1", "2026-04-23", "09:30", "Dr. Lima", AppointmentStatus.CONFIRMED)
    canceled = Appointment("a3", "p1", "2026-04-25", "11:00", "Dr. Lima", AppointmentStatus.CANCELED)

    assert ConversationOperation.LIST_APPOINTMENTS.requires_verification is True
    assert ConversationOperation.HELP.requires_verification is False
    assert scheduled.is_confirmable is True
    assert confirmed.is_confirmable is False
    assert confirmed.is_cancelable is True
    assert canceled.is_cancelable is False
    assert scheduled.is_owned_by("p1") is True
    assert scheduled.is_owned_by("p2") is False
