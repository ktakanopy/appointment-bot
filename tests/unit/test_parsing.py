from app.graph import parsing
from app.models import ConversationOperation, DateOfBirth, Phone


def test_normalize_helpers_parse_supported_identity_fields():
    assert Phone("(11) 99999-8888").digits == "11999998888"
    assert DateOfBirth("10/05/1990").value == "1990-05-10"
    assert parsing.extract_full_name("ana silva") == "Ana Silva"
    assert parsing.extract_full_name("my phone number is 11999998888") is None
    assert parsing.extract_full_name("I want to see my appointments, I'm Ana Silva") == "Ana Silva"


def test_extract_requested_action_prefers_protected_keywords():
    assert (
        parsing.extract_requested_operation("Please cancel my appointment", {})
        == ConversationOperation.CANCEL_APPOINTMENT
    )
    assert (
        parsing.extract_requested_operation("Show my appointments", {})
        == ConversationOperation.LIST_APPOINTMENTS
    )
    assert parsing.extract_requested_operation("What can you do?", {}) == ConversationOperation.HELP


def test_resolve_appointment_reference_supports_ordinals_and_dates():
    from app.models import Appointment, AppointmentStatus

    appointments = [
        Appointment("a1", "p1", "2026-04-20", "14:00", "Dr. Costa", AppointmentStatus.SCHEDULED),
        Appointment("a2", "p1", "2026-04-23", "09:30", "Dr. Lima", AppointmentStatus.CONFIRMED),
    ]

    assert parsing.resolve_appointment_reference("0", appointments) == appointments[0]
    assert parsing.resolve_appointment_reference("1", appointments) == appointments[0]
    assert parsing.resolve_appointment_reference("2", appointments) == appointments[1]
    assert parsing.resolve_appointment_reference("2026-04-23", appointments) == appointments[1]


def test_resolve_appointment_reference_returns_none_for_duplicate_date_matches():
    from app.models import Appointment, AppointmentStatus

    appointments = [
        Appointment("a1", "p1", "2026-04-20", "09:00", "Dr. Costa", AppointmentStatus.SCHEDULED),
        Appointment("a2", "p1", "2026-04-20", "14:00", "Dr. Lima", AppointmentStatus.SCHEDULED),
    ]

    assert parsing.resolve_appointment_reference("2026-04-20", appointments) is None
