from __future__ import annotations

from app.models import (
    Appointment,
    AppointmentStatus,
    DateOfBirth,
    FullName,
    Patient,
    Phone,
    SessionRecord,
)


class InMemoryPatientRepository:
    def __init__(self, patients: list[Patient] | None = None):
        self._patients = patients or [
            Patient(
                id="p1",
                full_name=FullName("Ana Silva"),
                phone=Phone("11999998888"),
                date_of_birth=DateOfBirth("1990-05-10"),
            ),
            Patient(
                id="p2",
                full_name=FullName("Carlos Souza"),
                phone=Phone("11911112222"),
                date_of_birth=DateOfBirth("1985-09-22"),
            ),
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
                    Appointment(
                        id="a1",
                        patient_id="p1",
                        date="2026-04-20",
                        time="14:00",
                        doctor="Dr. Costa",
                        status=AppointmentStatus.SCHEDULED,
                    ),
                    Appointment(
                        id="a2",
                        patient_id="p1",
                        date="2026-04-23",
                        time="09:30",
                        doctor="Dr. Lima",
                        status=AppointmentStatus.CONFIRMED,
                    ),
                    Appointment(
                        id="a3",
                        patient_id="p2",
                        date="2026-04-25",
                        time="11:00",
                        doctor="Dr. Costa",
                        status=AppointmentStatus.SCHEDULED,
                    ),
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


class InMemorySessionStore:
    def __init__(self):
        self._sessions: dict[str, SessionRecord] = {}

    def get(self, session_id: str) -> SessionRecord | None:
        return self._sessions.get(session_id)

    def save(self, session: SessionRecord) -> SessionRecord:
        self._sessions[session.session_id] = session
        return session

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def list(self) -> list[SessionRecord]:
        return list(self._sessions.values())
