from __future__ import annotations

from app.domain.models import (
    Appointment,
    AppointmentStatus,
    DateOfBirth,
    FullName,
    Patient,
    Phone,
)


class InMemoryPatientRepository:
    def __init__(self, patients: list[Patient] | None = None):
        self._patients = patients or [
            Patient("p1", FullName("Ana Silva"), Phone("11999998888"), DateOfBirth("1990-05-10")),
            Patient("p2", FullName("Carlos Souza"), Phone("11911112222"), DateOfBirth("1985-09-22")),
        ]

    def find_by_identity(self, full_name: FullName, phone: Phone, dob: DateOfBirth) -> Patient | None:
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

    def save(self, appointment: Appointment) -> Appointment:
        self._appointments[appointment.id] = appointment
        return appointment
