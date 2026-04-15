from __future__ import annotations

from app.domain.models import Appointment, AppointmentStatus

PROTECTED_ACTIONS = {"list_appointments", "confirm_appointment", "cancel_appointment"}


def requires_verification(action: str | None) -> bool:
    return action in PROTECTED_ACTIONS


def missing_verification_fields(state: dict) -> list[str]:
    verification = state.get("verification", {})
    missing_fields = getattr(verification, "missing_fields", None)
    if callable(missing_fields):
        return missing_fields()
    missing = []
    if not verification.get("provided_full_name"):
        missing.append("full_name")
    if not verification.get("provided_phone"):
        missing.append("phone")
    if not verification.get("provided_dob"):
        missing.append("dob")
    return missing


def appointment_is_owned_by_patient(appointment: Appointment | None, patient_id: str | None) -> bool:
    return bool(appointment and patient_id and appointment.patient_id == patient_id)


def can_confirm(appointment: Appointment) -> bool:
    return appointment.status == AppointmentStatus.SCHEDULED


def can_cancel(appointment: Appointment) -> bool:
    return appointment.status in {AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED}
