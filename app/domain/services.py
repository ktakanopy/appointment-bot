from __future__ import annotations

from app.domain.models import ActionResult, Appointment, AppointmentStatus, Patient
from app.domain.policies import normalize_dob, normalize_name, normalize_phone


class RepositoryUnavailableError(RuntimeError):
    pass


class VerificationService:
    def __init__(self, patient_repository):
        self.patient_repository = patient_repository

    def verify_identity(self, full_name: str, phone: str, dob: str) -> Patient | None:
        try:
            return self.patient_repository.find_by_identity(
                normalize_name(full_name),
                normalize_phone(phone),
                normalize_dob(dob) or dob,
            )
        except Exception as error:  # pragma: no cover - defensive boundary
            raise RepositoryUnavailableError("patient repository unavailable") from error


class AppointmentService:
    def __init__(self, appointment_repository):
        self.appointment_repository = appointment_repository

    def list_appointments(self, patient_id: str) -> list[Appointment]:
        try:
            return self.appointment_repository.list_by_patient(patient_id)
        except Exception as error:  # pragma: no cover - defensive boundary
            raise RepositoryUnavailableError("appointment repository unavailable") from error

    def get_appointment(self, appointment_id: str) -> Appointment | None:
        try:
            return self.appointment_repository.get_by_id(appointment_id)
        except Exception as error:  # pragma: no cover - defensive boundary
            raise RepositoryUnavailableError("appointment repository unavailable") from error

    def confirm_appointment(self, patient_id: str, appointment_id: str) -> tuple[Appointment, ActionResult]:
        appointment = self.get_appointment(appointment_id)
        if appointment is None:
            raise ValueError("appointment not found")
        try:
            updated = self.appointment_repository.confirm(patient_id, appointment_id)
        except Exception as error:  # pragma: no cover - defensive boundary
            raise RepositoryUnavailableError("appointment repository unavailable") from error

        outcome = "already_confirmed" if appointment.status == AppointmentStatus.CONFIRMED else "confirmed"
        return updated, ActionResult("confirm_appointment", outcome, appointment_id)

    def cancel_appointment(self, patient_id: str, appointment_id: str) -> tuple[Appointment, ActionResult]:
        appointment = self.get_appointment(appointment_id)
        if appointment is None:
            raise ValueError("appointment not found")
        try:
            updated = self.appointment_repository.cancel(patient_id, appointment_id)
        except Exception as error:  # pragma: no cover - defensive boundary
            raise RepositoryUnavailableError("appointment repository unavailable") from error

        outcome = "already_canceled" if appointment.status == AppointmentStatus.CANCELED else "canceled"
        return updated, ActionResult("cancel_appointment", outcome, appointment_id)
