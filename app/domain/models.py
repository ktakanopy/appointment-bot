from __future__ import annotations

from datetime import datetime
from datetime import datetime as dt
from enum import Enum

from pydantic import BaseModel, ConfigDict, field_validator


class AppointmentStatus(str, Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    CANCELED = "canceled"


class AppointmentMutationOutcome(str, Enum):
    CONFIRMED = "confirmed"
    ALREADY_CONFIRMED = "already_confirmed"
    CANCELED = "canceled"
    ALREADY_CANCELED = "already_canceled"


class FullName(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: str

    def __init__(self, raw: str):
        super().__init__(value=raw)

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str) -> str:
        normalized = " ".join(part for part in value.strip().split())
        if len(normalized.split()) < 2:
            raise ValueError("full name requires first and last name")
        return normalized.title()

    def __str__(self) -> str:
        return self.value


class Phone(BaseModel):
    model_config = ConfigDict(frozen=True)

    digits: str

    def __init__(self, raw: str):
        super().__init__(digits=raw)

    @field_validator("digits")
    @classmethod
    def validate_digits(cls, value: str) -> str:
        digits = "".join(character for character in value if character.isdigit())
        if len(digits) < 10:
            raise ValueError("phone requires at least 10 digits")
        return digits

    def __str__(self) -> str:
        return self.digits


class DateOfBirth(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: str

    def __init__(self, raw: str):
        super().__init__(value=raw)

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str) -> str:
        cleaned = value.strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return dt.strptime(cleaned, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        raise ValueError("date of birth must use YYYY-MM-DD or DD/MM/YYYY")

    def __str__(self) -> str:
        return self.value


class Patient(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    full_name: FullName
    phone: Phone
    date_of_birth: DateOfBirth

    def __init__(self, id: str, full_name: FullName, phone: Phone, date_of_birth: DateOfBirth):
        super().__init__(
            id=id,
            full_name=full_name,
            phone=phone,
            date_of_birth=date_of_birth,
        )


class Appointment(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    patient_id: str
    date: str
    time: str
    doctor: str
    status: AppointmentStatus

    def __init__(
        self,
        id: str,
        patient_id: str,
        date: str,
        time: str,
        doctor: str,
        status: AppointmentStatus,
    ):
        super().__init__(
            id=id,
            patient_id=patient_id,
            date=date,
            time=time,
            doctor=doctor,
            status=status,
        )

    def confirm(self) -> tuple[Appointment, AppointmentMutationOutcome]:
        if self.status == AppointmentStatus.CONFIRMED:
            return self, AppointmentMutationOutcome.ALREADY_CONFIRMED
        if self.status != AppointmentStatus.SCHEDULED:
            from app.domain.errors import AppointmentNotConfirmableError

            raise AppointmentNotConfirmableError(self.id)
        return self.model_copy(update={"status": AppointmentStatus.CONFIRMED}), AppointmentMutationOutcome.CONFIRMED

    def cancel(self) -> tuple[Appointment, AppointmentMutationOutcome]:
        if self.status == AppointmentStatus.CANCELED:
            return self, AppointmentMutationOutcome.ALREADY_CANCELED
        if self.status not in {AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED}:
            from app.domain.errors import AppointmentNotCancelableError

            raise AppointmentNotCancelableError(self.id)
        return self.model_copy(update={"status": AppointmentStatus.CANCELED}), AppointmentMutationOutcome.CANCELED

    def is_owned_by(self, patient_id: str | None) -> bool:
        return bool(patient_id and self.patient_id == patient_id)

    @property
    def is_confirmable(self) -> bool:
        return self.status == AppointmentStatus.SCHEDULED

    @property
    def is_cancelable(self) -> bool:
        return self.status in {AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED}


class RememberedIdentityStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    UNAVAILABLE = "unavailable"


class RememberedIdentity(BaseModel):
    model_config = ConfigDict(frozen=True)

    remembered_identity_id: str
    patient_id: str
    display_name: str | None
    verification_fingerprint: str
    issued_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    status: RememberedIdentityStatus

    def __init__(
        self,
        remembered_identity_id: str,
        patient_id: str,
        display_name: str | None,
        verification_fingerprint: str,
        issued_at: datetime,
        expires_at: datetime,
        revoked_at: datetime | None,
        status: RememberedIdentityStatus,
    ):
        super().__init__(
            remembered_identity_id=remembered_identity_id,
            patient_id=patient_id,
            display_name=display_name,
            verification_fingerprint=verification_fingerprint,
            issued_at=issued_at,
            expires_at=expires_at,
            revoked_at=revoked_at,
            status=status,
        )

    def is_active(self, now: datetime) -> bool:
        return self.revoked_at is None and self.expires_at > now and self.status == RememberedIdentityStatus.ACTIVE

    def expire(self) -> RememberedIdentity:
        if self.revoked_at is not None:
            return self.model_copy(update={"status": RememberedIdentityStatus.REVOKED})
        return self.model_copy(update={"status": RememberedIdentityStatus.EXPIRED})

    def revoke(self, now: datetime) -> RememberedIdentity:
        return self.model_copy(
            update={
                "revoked_at": now,
                "status": RememberedIdentityStatus.REVOKED,
            }
        )
