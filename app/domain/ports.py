from __future__ import annotations

from typing import Protocol

from app.domain.models import Appointment, DateOfBirth, FullName, Patient, Phone, RememberedIdentity


class AppointmentRepository(Protocol):
    def list_by_patient(self, patient_id: str) -> list[Appointment]:
        ...

    def get_by_id(self, appointment_id: str) -> Appointment | None:
        ...

    def save(self, appointment: Appointment) -> Appointment:
        ...


class PatientRepository(Protocol):
    def find_by_identity(self, full_name: FullName, phone: Phone, dob: DateOfBirth) -> Patient | None:
        ...


class RememberedIdentityRepository(Protocol):
    def get_by_id(self, remembered_identity_id: str) -> RememberedIdentity | None:
        ...

    def get_active_by_patient_id(self, patient_id: str) -> RememberedIdentity | None:
        ...

    def save(self, identity: RememberedIdentity) -> RememberedIdentity:
        ...

    def revoke(self, remembered_identity_id: str) -> bool:
        ...
