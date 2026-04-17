from __future__ import annotations

from typing import Protocol

from app.models import Appointment, Patient, DateOfBirth, FullName, Phone


class PatientRepository(Protocol):
    def find_by_identity(self, full_name: FullName, phone: Phone, dob: DateOfBirth) -> Patient | None: ...


class AppointmentRepository(Protocol):
    def list_by_patient(self, patient_id: str) -> list[Appointment]: ...
    def get_by_id(self, appointment_id: str) -> Appointment | None: ...
    def save(self, appointment: Appointment) -> Appointment: ...
