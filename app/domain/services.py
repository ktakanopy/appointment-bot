from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Callable
from uuid import uuid4

from app.domain.errors import (
    AppointmentNotCancelableError,
    AppointmentNotConfirmableError,
    AppointmentNotOwnedError,
    RepositoryUnavailableError,
)
from app.domain.models import (
    ActionResult,
    Appointment,
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
        try:
            return self.patient_repository.find_by_identity(
                FullName(full_name),
                Phone(phone),
                DateOfBirth(dob),
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
            if not appointment.is_owned_by(patient_id):
                raise AppointmentNotOwnedError(appointment_id)
            updated, outcome = appointment.confirm()
            saved = self.appointment_repository.save(updated)
        except Exception as error:  # pragma: no cover - defensive boundary
            if isinstance(error, (AppointmentNotOwnedError, AppointmentNotConfirmableError)):
                raise
            raise RepositoryUnavailableError("appointment repository unavailable") from error

        return saved, ActionResult("confirm_appointment", outcome, appointment_id)

    def cancel_appointment(self, patient_id: str, appointment_id: str) -> tuple[Appointment, ActionResult]:
        appointment = self.get_appointment(appointment_id)
        if appointment is None:
            raise ValueError("appointment not found")
        try:
            if not appointment.is_owned_by(patient_id):
                raise AppointmentNotOwnedError(appointment_id)
            updated, outcome = appointment.cancel()
            saved = self.appointment_repository.save(updated)
        except Exception as error:  # pragma: no cover - defensive boundary
            if isinstance(error, (AppointmentNotOwnedError, AppointmentNotCancelableError)):
                raise
            raise RepositoryUnavailableError("appointment repository unavailable") from error

        return saved, ActionResult("cancel_appointment", outcome, appointment_id)


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
        return identity.model_copy(
            update={
                "status": (
                    RememberedIdentityStatus.EXPIRED
                    if identity.revoked_at is None
                    else RememberedIdentityStatus.REVOKED
                )
            }
        )

    def _is_active(self, identity: RememberedIdentity) -> bool:
        if identity.revoked_at is not None:
            return False
        return identity.expires_at > self.now_factory()

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
