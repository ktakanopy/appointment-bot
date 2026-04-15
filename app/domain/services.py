from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Callable
from uuid import uuid4

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
    RememberedIdentity,
    RememberedIdentityStatus,
)
from app.domain.ports import AppointmentRepository, PatientRepository, RememberedIdentityRepository


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


class RememberedIdentityService:
    def __init__(
        self,
        identity_repository: RememberedIdentityRepository,
        ttl_hours: int,
        now_factory: Callable[[], datetime] | None = None,
    ):
        self.identity_repository = identity_repository
        self.ttl_hours = ttl_hours
        self.now_factory = now_factory or (lambda: datetime.now(UTC))

    def build_fingerprint(self, full_name: str | None, phone: str | None, dob: str | None, patient_id: str) -> str:
        payload = "|".join(
            [
                self._normalize_full_name(full_name),
                self._normalize_phone(phone),
                self._normalize_dob(dob),
                patient_id,
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def ensure_identity(
        self,
        patient_id: str,
        display_name: str | None,
        verification_fingerprint: str,
    ) -> RememberedIdentity:
        existing = self.identity_repository.get_active_by_patient_id(patient_id)
        if existing and existing.is_active(self.now_factory()):
            return existing
        now = self.now_factory()
        identity = RememberedIdentity(
            remembered_identity_id=str(uuid4()),
            patient_id=patient_id,
            display_name=display_name,
            verification_fingerprint=verification_fingerprint,
            issued_at=now,
            expires_at=now + timedelta(hours=self.ttl_hours),
            revoked_at=None,
            status=RememberedIdentityStatus.ACTIVE,
        )
        return self.identity_repository.save(identity)

    def restore_identity(self, remembered_identity_id: str | None) -> RememberedIdentity | None:
        if not remembered_identity_id:
            return None
        identity = self.identity_repository.get_by_id(remembered_identity_id)
        if identity is None:
            return None
        if not identity.is_active(self.now_factory()):
            expired = identity.expire()
            self.identity_repository.save(expired)
            return expired
        return identity

    def revoke_identity(self, remembered_identity_id: str) -> bool:
        return self.identity_repository.revoke(remembered_identity_id)

    def _normalize_full_name(self, value: str | None) -> str:
        if not value:
            return ""
        return FullName(value).value

    def _normalize_phone(self, value: str | None) -> str:
        if not value:
            return ""
        return Phone(value).digits

    def _normalize_dob(self, value: str | None) -> str:
        if not value:
            return ""
        return DateOfBirth(value).value
