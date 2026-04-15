import pytest

from app.graph.state import ConversationState, VerificationState
from app.models import Appointment, AppointmentStatus, ConversationOperation, ResponseKey
from app.responses import STATIC_RESPONSES, build_response_text


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


def test_static_responses_cover_all_non_dynamic_response_keys():
    dynamic_keys = {
        ResponseKey.APPOINTMENTS_LIST,
        ResponseKey.CONFIRM_SUCCESS,
        ResponseKey.CONFIRM_ALREADY_CONFIRMED,
        ResponseKey.CANCEL_SUCCESS,
        ResponseKey.CANCEL_ALREADY_CANCELED,
    }
    assert set(STATIC_RESPONSES) == set(ResponseKey) - dynamic_keys


@pytest.mark.parametrize("response_key", list(ResponseKey))
def test_build_response_text_returns_text_for_every_response_key(response_key: ResponseKey):
    state = ConversationState(thread_id="thread-1")
    if response_key in {
        ResponseKey.CONFIRM_SUCCESS,
        ResponseKey.CONFIRM_ALREADY_CONFIRMED,
        ResponseKey.CANCEL_SUCCESS,
        ResponseKey.CANCEL_ALREADY_CANCELED,
    }:
        state.turn.subject_appointment = Appointment(
            id="a1",
            patient_id="p1",
            date="2026-04-20",
            time="14:00",
            doctor="Dr. Costa",
            status=AppointmentStatus.SCHEDULED,
        )
    if response_key == ResponseKey.APPOINTMENTS_LIST:
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
    state.turn.response_key = response_key

    assert build_response_text(state)
