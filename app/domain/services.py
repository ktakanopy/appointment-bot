from __future__ import annotations

from app.domain.errors import (
    AppointmentNotFoundError,
    AppointmentNotOwnedError,
)
from app.domain.models import (
    Appointment,
    AppointmentMutationOutcome,
    DateOfBirth,
    FullName,
    Patient,
    Phone,
)
from app.domain.ports import AppointmentRepository, PatientRepository


class VerificationService:
    def __init__(self, patient_repository: PatientRepository):
        self.patient_repository = patient_repository

    def verify_identity(self, full_name: str, phone: str, dob: str) -> Patient | None:
        return self.patient_repository.find_by_identity(
            FullName(full_name),
            Phone(phone),
            DateOfBirth(dob),
        )


class AppointmentService:
    def __init__(self, appointment_repository: AppointmentRepository):
        self.appointment_repository = appointment_repository

    def list_appointments(self, patient_id: str) -> list[Appointment]:
        return self.appointment_repository.list_by_patient(patient_id)

    def get_appointment(self, appointment_id: str) -> Appointment | None:
        return self.appointment_repository.get_by_id(appointment_id)

    def confirm_appointment(
        self,
        patient_id: str,
        appointment_id: str,
    ) -> tuple[Appointment, AppointmentMutationOutcome]:
        appointment = self.get_appointment(appointment_id)
        if appointment is None:
            raise AppointmentNotFoundError(appointment_id)
        if not appointment.is_owned_by(patient_id):
            raise AppointmentNotOwnedError(appointment_id)
        updated, outcome = appointment.confirm()
        saved = self.appointment_repository.save(updated)
        return saved, outcome

    def cancel_appointment(
        self,
        patient_id: str,
        appointment_id: str,
    ) -> tuple[Appointment, AppointmentMutationOutcome]:
        appointment = self.get_appointment(appointment_id)
        if appointment is None:
            raise AppointmentNotFoundError(appointment_id)
        if not appointment.is_owned_by(patient_id):
            raise AppointmentNotOwnedError(appointment_id)
        updated, outcome = appointment.cancel()
        saved = self.appointment_repository.save(updated)
        return saved, outcome
