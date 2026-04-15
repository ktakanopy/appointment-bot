from app.domain import policies


def test_missing_verification_fields_tracks_unset_values():
    state = {
        "verification": {
            "provided_full_name": "Ana Silva",
            "provided_phone": None,
            "provided_dob": None,
        }
    }

    assert policies.missing_verification_fields(state) == ["phone", "dob"]


def test_appointment_policies_cover_status_rules_and_ownership():
    from app.domain.models import Appointment, AppointmentStatus

    scheduled = Appointment("a1", "p1", "2026-04-20", "14:00", "Dr. Costa", AppointmentStatus.SCHEDULED)
    confirmed = Appointment("a2", "p1", "2026-04-23", "09:30", "Dr. Lima", AppointmentStatus.CONFIRMED)
    canceled = Appointment("a3", "p1", "2026-04-25", "11:00", "Dr. Lima", AppointmentStatus.CANCELED)

    assert policies.requires_verification("list_appointments") is True
    assert policies.requires_verification("help") is False
    assert policies.can_confirm(scheduled) is True
    assert policies.can_confirm(confirmed) is False
    assert policies.can_cancel(confirmed) is True
    assert policies.can_cancel(canceled) is False
    assert policies.appointment_is_owned_by_patient(scheduled, "p1") is True
    assert policies.appointment_is_owned_by_patient(scheduled, "p2") is False
