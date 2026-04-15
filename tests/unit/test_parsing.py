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
        Appointment(
            id="a1",
            patient_id="p1",
            date="2026-04-20",
            time="14:00",
            doctor="Dr. Costa",
            status=AppointmentStatus.SCHEDULED,
        ),
        Appointment(
            id="a2",
            patient_id="p1",
            date="2026-04-23",
            time="09:30",
            doctor="Dr. Lima",
            status=AppointmentStatus.CONFIRMED,
        ),
    ]

    assert parsing.resolve_appointment_reference("0", appointments) == appointments[0]
    assert parsing.resolve_appointment_reference("1", appointments) == appointments[0]
    assert parsing.resolve_appointment_reference("2", appointments) == appointments[1]
    assert parsing.resolve_appointment_reference("2026-04-23", appointments) == appointments[1]


def test_resolve_appointment_reference_returns_none_for_duplicate_date_matches():
    from app.models import Appointment, AppointmentStatus

    appointments = [
        Appointment(
            id="a1",
            patient_id="p1",
            date="2026-04-20",
            time="09:00",
            doctor="Dr. Costa",
            status=AppointmentStatus.SCHEDULED,
        ),
        Appointment(
            id="a2",
            patient_id="p1",
            date="2026-04-20",
            time="14:00",
            doctor="Dr. Lima",
            status=AppointmentStatus.SCHEDULED,
        ),
    ]

    assert parsing.resolve_appointment_reference("2026-04-20", appointments) is None
