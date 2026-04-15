from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Callable
from uuid import uuid4

from app.domain.models import (
    ActionResult,
    Appointment,
    AppointmentStatus,
    Patient,
    RememberedIdentity,
    RememberedIdentityStatus,
)
from app.domain.parsing import normalize_dob, normalize_name, normalize_phone
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.patient_repository import PatientRepository
from app.repositories.remembered_identity_repository import RememberedIdentityRepository


class RepositoryUnavailableError(RuntimeError):
    pass


class VerificationService:
    def __init__(self, patient_repository: PatientRepository):
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
    def __init__(self, appointment_repository: AppointmentRepository):
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
                normalize_name(full_name or ""),
                normalize_phone(phone or ""),
                normalize_dob(dob or "") or (dob or ""),
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
        if existing and self._is_active(existing):
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
        if not self._is_active(identity):
            expired = self._mark_expired(identity)
            self.identity_repository.save(expired)
            return expired
        return identity

    def revoke_identity(self, remembered_identity_id: str) -> bool:
        return self.identity_repository.revoke(remembered_identity_id)

    def summary_for_identity(self, identity: RememberedIdentity | None) -> dict[str, str | None]:
        if identity is None:
            return {
                "remembered_identity_id": "",
                "status": RememberedIdentityStatus.UNAVAILABLE.value,
                "display_name": None,
                "expires_at": None,
            }
        return {
            "remembered_identity_id": identity.remembered_identity_id,
            "status": identity.status.value,
            "display_name": identity.display_name,
            "expires_at": identity.expires_at.isoformat(),
        }

    def _mark_expired(self, identity: RememberedIdentity) -> RememberedIdentity:
        return replace(
            identity,
            status=RememberedIdentityStatus.EXPIRED if identity.revoked_at is None else RememberedIdentityStatus.REVOKED,
        )

    def _is_active(self, identity: RememberedIdentity) -> bool:
        if identity.revoked_at is not None:
            return False
        return identity.expires_at > self.now_factory()
