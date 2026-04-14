from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class AppointmentStatus(str, Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    CANCELED = "canceled"


@dataclass(slots=True)
class Patient:
    id: str
    full_name: str
    phone: str
    date_of_birth: str


@dataclass(slots=True)
class Appointment:
    id: str
    patient_id: str
    date: str
    time: str
    doctor: str
    status: AppointmentStatus


@dataclass(slots=True)
class ActionResult:
    action: str
    outcome: str
    appointment_id: str | None = None


class RememberedIdentityStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    UNAVAILABLE = "unavailable"


@dataclass(slots=True)
class RememberedIdentity:
    remembered_identity_id: str
    patient_id: str
    display_name: str | None
    verification_fingerprint: str
    issued_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    status: RememberedIdentityStatus
