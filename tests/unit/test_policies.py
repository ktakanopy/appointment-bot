import pytest

from app.application.contracts.conversation import (
    ConversationOperation,
    ConversationWorkflowResult,
    ResponseKey,
    TurnSnapshot,
)
from app.application.contracts.workflow_dtos import WorkflowAppointmentSnapshot
from app.application.services.response_policy import ResponsePolicy
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


def test_response_policy_registry_covers_every_response_key():
    policy = ResponsePolicy()

    assert policy.covered_response_keys() == set(ResponseKey)


@pytest.mark.parametrize("response_key", list(ResponseKey))
def test_response_policy_builds_text_for_every_response_key(response_key: ResponseKey):
    policy = ResponsePolicy()
    subject = None
    listed_appointments = []
    if response_key in {
        ResponseKey.CONFIRM_SUCCESS,
        ResponseKey.CONFIRM_ALREADY_CONFIRMED,
        ResponseKey.CANCEL_SUCCESS,
        ResponseKey.CANCEL_ALREADY_CANCELED,
    }:
        subject = WorkflowAppointmentSnapshot(
            id="a1",
            date="2026-04-20",
            time="14:00",
            doctor="Dr. Costa",
            status="scheduled",
        )
    if response_key == ResponseKey.APPOINTMENTS_LIST:
        listed_appointments = [
            WorkflowAppointmentSnapshot(
                id="a1",
                date="2026-04-20",
                time="14:00",
                doctor="Dr. Costa",
                status="scheduled",
            )
        ]
    workflow_result = ConversationWorkflowResult(
        thread_id="thread-1",
        turn=TurnSnapshot(
            response_key=response_key,
            subject_appointment=subject,
        ),
        listed_appointments=listed_appointments,
    )

    assert policy.build_fallback_text(workflow_result)
