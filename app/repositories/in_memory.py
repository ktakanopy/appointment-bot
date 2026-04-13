from __future__ import annotations

from dataclasses import replace

from app.domain.models import Appointment, AppointmentStatus, Patient


class InMemoryPatientRepository:
    def __init__(self, patients: list[Patient] | None = None):
        self._patients = patients or [
            Patient("p1", "Ana Silva", "11999998888", "1990-05-10"),
            Patient("p2", "Carlos Souza", "11911112222", "1985-09-22"),
        ]

    def find_by_identity(self, full_name: str, phone: str, dob: str) -> Patient | None:
        for patient in self._patients:
            if patient.full_name == full_name and patient.phone == phone and patient.date_of_birth == dob:
                return patient
        return None


class InMemoryAppointmentRepository:
    def __init__(self, appointments: list[Appointment] | None = None):
        self._appointments = {
            appointment.id: appointment
            for appointment in (
                appointments
                or [
                    Appointment("a1", "p1", "2026-04-20", "14:00", "Dr. Costa", AppointmentStatus.SCHEDULED),
                    Appointment("a2", "p1", "2026-04-23", "09:30", "Dr. Lima", AppointmentStatus.CONFIRMED),
                    Appointment("a3", "p2", "2026-04-25", "11:00", "Dr. Costa", AppointmentStatus.SCHEDULED),
                ]
            )
        }

    def list_by_patient(self, patient_id: str) -> list[Appointment]:
        appointments = [appointment for appointment in self._appointments.values() if appointment.patient_id == patient_id]
        return sorted(appointments, key=lambda appointment: (appointment.date, appointment.time, appointment.id))

    def get_by_id(self, appointment_id: str) -> Appointment | None:
        return self._appointments.get(appointment_id)

    def confirm(self, patient_id: str, appointment_id: str) -> Appointment:
        appointment = self._appointments[appointment_id]
        if appointment.patient_id != patient_id:
            raise ValueError("appointment does not belong to patient")
        if appointment.status != AppointmentStatus.CONFIRMED:
            appointment = replace(appointment, status=AppointmentStatus.CONFIRMED)
            self._appointments[appointment_id] = appointment
        return appointment

    def cancel(self, patient_id: str, appointment_id: str) -> Appointment:
        appointment = self._appointments[appointment_id]
        if appointment.patient_id != patient_id:
            raise ValueError("appointment does not belong to patient")
        if appointment.status != AppointmentStatus.CANCELED:
            appointment = replace(appointment, status=AppointmentStatus.CANCELED)
            self._appointments[appointment_id] = appointment
        return appointment
