from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.errors import AppointmentNotConfirmableError
from app.domain.models import Appointment, AppointmentStatus


def test_appointment_confirm_is_idempotent_for_confirmed_status():
    appointment = Appointment("a1", "p1", "2026-04-20", "14:00", "Dr. Costa", AppointmentStatus.CONFIRMED)

    updated, outcome = appointment.confirm()

    assert updated is appointment
    assert outcome == "already_confirmed"


def test_appointment_confirm_transitions_scheduled_status():
    appointment = Appointment("a1", "p1", "2026-04-20", "14:00", "Dr. Costa", AppointmentStatus.SCHEDULED)

    updated, outcome = appointment.confirm()

    assert updated.status == AppointmentStatus.CONFIRMED
    assert outcome == "confirmed"


def test_appointment_confirm_rejects_canceled_status():
    appointment = Appointment("a1", "p1", "2026-04-20", "14:00", "Dr. Costa", AppointmentStatus.CANCELED)

    with pytest.raises(AppointmentNotConfirmableError):
        appointment.confirm()


def test_appointment_cancel_is_idempotent_for_canceled_status():
    appointment = Appointment("a1", "p1", "2026-04-20", "14:00", "Dr. Costa", AppointmentStatus.CANCELED)

    updated, outcome = appointment.cancel()

    assert updated is appointment
    assert outcome == "already_canceled"


def test_appointment_cancel_transitions_scheduled_or_confirmed_status():
    scheduled = Appointment("a1", "p1", "2026-04-20", "14:00", "Dr. Costa", AppointmentStatus.SCHEDULED)
    confirmed = Appointment("a2", "p1", "2026-04-23", "09:30", "Dr. Lima", AppointmentStatus.CONFIRMED)

    scheduled_updated, scheduled_outcome = scheduled.cancel()
    confirmed_updated, confirmed_outcome = confirmed.cancel()

    assert scheduled_updated.status == AppointmentStatus.CANCELED
    assert scheduled_outcome == "canceled"
    assert confirmed_updated.status == AppointmentStatus.CANCELED
    assert confirmed_outcome == "canceled"


def test_appointment_cancel_rejects_unhandled_status():
    class UnknownStatus(str):
        pass

    with pytest.raises(ValidationError):
        Appointment("a1", "p1", "2026-04-20", "14:00", "Dr. Costa", UnknownStatus("other"))


def test_appointment_ownership_and_state_properties():
    appointment = Appointment("a1", "p1", "2026-04-20", "14:00", "Dr. Costa", AppointmentStatus.SCHEDULED)

    assert appointment.is_owned_by("p1") is True
    assert appointment.is_owned_by("p2") is False
    assert appointment.is_confirmable is True
    assert appointment.is_cancelable is True
