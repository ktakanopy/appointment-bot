import pytest

from app.domain.models import AppointmentStatus
from app.repositories.in_memory import InMemoryAppointmentRepository


def test_list_by_patient_returns_only_owned_appointments():
    repository = InMemoryAppointmentRepository()

    appointments = repository.list_by_patient("p1")

    assert len(appointments) == 2
    assert all(appointment.patient_id == "p1" for appointment in appointments)


def test_confirm_and_cancel_are_idempotent_for_same_patient():
    repository = InMemoryAppointmentRepository()

    confirmed = repository.confirm("p1", "a1")
    confirmed_again = repository.confirm("p1", "a1")
    canceled = repository.cancel("p1", "a1")
    canceled_again = repository.cancel("p1", "a1")

    assert confirmed.status == AppointmentStatus.CONFIRMED
    assert confirmed_again.status == AppointmentStatus.CONFIRMED
    assert canceled.status == AppointmentStatus.CANCELED
    assert canceled_again.status == AppointmentStatus.CANCELED


def test_repository_rejects_wrong_patient_mutation():
    repository = InMemoryAppointmentRepository()

    with pytest.raises(ValueError):
        repository.confirm("p1", "a3")
