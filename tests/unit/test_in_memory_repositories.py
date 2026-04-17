from app.models import AppointmentStatus
from app.repositories import InMemoryAppointmentRepository


def test_list_by_patient_returns_only_owned_appointments():
    repository = InMemoryAppointmentRepository()

    appointments = repository.list_by_patient("p1")

    assert len(appointments) == 2
    assert all(appointment.patient_id == "p1" for appointment in appointments)


def test_confirm_and_cancel_are_idempotent_for_same_patient():
    repository = InMemoryAppointmentRepository()

    appointment = repository.get_by_id("a1")
    confirmed, _ = appointment.confirm()
    repository.save(confirmed)
    confirmed_again, _ = repository.get_by_id("a1").confirm()
    repository.save(confirmed_again)
    canceled, _ = repository.get_by_id("a1").cancel()
    repository.save(canceled)
    canceled_again, _ = repository.get_by_id("a1").cancel()
    repository.save(canceled_again)

    assert confirmed.status == AppointmentStatus.CONFIRMED
    assert confirmed_again.status == AppointmentStatus.CONFIRMED
    assert canceled.status == AppointmentStatus.CANCELED
    assert canceled_again.status == AppointmentStatus.CANCELED


def test_repository_rejects_wrong_patient_mutation():
    repository = InMemoryAppointmentRepository()
    appointment = repository.get_by_id("a3")

    assert appointment.is_owned_by("p1") is False
