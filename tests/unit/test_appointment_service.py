from __future__ import annotations

import pytest

from app.domain.errors import AppointmentNotFoundError, AppointmentNotOwnedError
from app.domain.models import AppointmentMutationOutcome, AppointmentStatus
from app.domain.services import AppointmentService
from app.infrastructure.persistence.in_memory import InMemoryAppointmentRepository


def test_appointment_service_lists_patient_appointments():
    service = AppointmentService(InMemoryAppointmentRepository())

    appointments = service.list_appointments("p1")

    assert len(appointments) == 2
    assert all(appointment.patient_id == "p1" for appointment in appointments)


def test_appointment_service_confirms_scheduled_appointment():
    service = AppointmentService(InMemoryAppointmentRepository())

    updated, action_result = service.confirm_appointment("p1", "a1")

    assert updated.status == AppointmentStatus.CONFIRMED
    assert action_result == AppointmentMutationOutcome.CONFIRMED


def test_appointment_service_reports_already_confirmed_appointment():
    service = AppointmentService(InMemoryAppointmentRepository())

    updated, action_result = service.confirm_appointment("p1", "a2")

    assert updated.status == AppointmentStatus.CONFIRMED
    assert action_result == AppointmentMutationOutcome.ALREADY_CONFIRMED


def test_appointment_service_cancels_appointment():
    service = AppointmentService(InMemoryAppointmentRepository())

    updated, action_result = service.cancel_appointment("p1", "a2")

    assert updated.status == AppointmentStatus.CANCELED
    assert action_result == AppointmentMutationOutcome.CANCELED


def test_appointment_service_reports_already_canceled_appointment():
    repository = InMemoryAppointmentRepository()
    appointment = repository.get_by_id("a1")
    canceled, _ = appointment.cancel()
    repository.save(canceled)
    service = AppointmentService(repository)

    updated, action_result = service.cancel_appointment("p1", "a1")

    assert updated.status == AppointmentStatus.CANCELED
    assert action_result == AppointmentMutationOutcome.ALREADY_CANCELED


def test_appointment_service_rejects_wrong_patient():
    service = AppointmentService(InMemoryAppointmentRepository())

    with pytest.raises(AppointmentNotOwnedError):
        service.confirm_appointment("p1", "a3")


def test_appointment_service_rejects_missing_appointment():
    service = AppointmentService(InMemoryAppointmentRepository())

    with pytest.raises(AppointmentNotFoundError):
        service.confirm_appointment("p1", "missing")
