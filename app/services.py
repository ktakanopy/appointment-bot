from __future__ import annotations

import time
from uuid import uuid4

from app.models import (
    ActionOutcome,
    Appointment,
    AppointmentNotFoundError,
    AppointmentNotOwnedError,
    DateOfBirth,
    FullName,
    Patient,
    Phone,
    SessionNotFoundError,
    SessionRecord,
)
from app.repositories import InMemorySessionStore


class VerificationService:
    def __init__(self, patient_repository):
        self.patient_repository = patient_repository

    def verify_identity(self, full_name: str, phone: str, dob: str) -> Patient | None:
        return self.patient_repository.find_by_identity(
            FullName(full_name),
            Phone(phone),
            DateOfBirth(dob),
        )


class AppointmentService:
    def __init__(self, appointment_repository):
        self.appointment_repository = appointment_repository

    def list_appointments(self, patient_id: str) -> list[Appointment]:
        return self.appointment_repository.list_by_patient(patient_id)

    def get_appointment(self, appointment_id: str) -> Appointment | None:
        return self.appointment_repository.get_by_id(appointment_id)

    def confirm_appointment(
        self,
        patient_id: str,
        appointment_id: str,
    ) -> tuple[Appointment, ActionOutcome]:
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
    ) -> tuple[Appointment, ActionOutcome]:
        appointment = self.get_appointment(appointment_id)
        if appointment is None:
            raise AppointmentNotFoundError(appointment_id)
        if not appointment.is_owned_by(patient_id):
            raise AppointmentNotOwnedError(appointment_id)
        updated, outcome = appointment.cancel()
        saved = self.appointment_repository.save(updated)
        return saved, outcome


class SessionService:
    def __init__(
        self,
        session_store: InMemorySessionStore,
        session_ttl_minutes: int,
    ):
        self.session_store = session_store
        self.session_ttl_seconds = session_ttl_minutes * 60

    def create_session(self) -> SessionRecord:
        session_id = str(uuid4())
        now = time.monotonic()
        session = SessionRecord(
            session_id=session_id,
            thread_id=session_id,
            created_at=now,
            last_seen_at=now,
        )
        return self.session_store.save(session)

    def cleanup_expired(self) -> None:
        now = time.monotonic()
        for session in self.session_store.list():
            if now - session.last_seen_at > self.session_ttl_seconds:
                self.session_store.delete(session.session_id)

    def require_session(self, session_id: str) -> SessionRecord:
        session = self.session_store.get(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        updated = session.model_copy(update={"last_seen_at": time.monotonic()})
        return self.session_store.save(updated)
