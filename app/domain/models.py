from __future__ import annotations

from dataclasses import dataclass
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
