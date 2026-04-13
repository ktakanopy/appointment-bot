from __future__ import annotations

from typing import Protocol

from app.domain.models import Appointment


class AppointmentRepository(Protocol):
    def list_by_patient(self, patient_id: str) -> list[Appointment]:
        ...

    def get_by_id(self, appointment_id: str) -> Appointment | None:
        ...

    def confirm(self, patient_id: str, appointment_id: str) -> Appointment:
        ...

    def cancel(self, patient_id: str, appointment_id: str) -> Appointment:
        ...
