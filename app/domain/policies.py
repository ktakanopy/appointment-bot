from __future__ import annotations

import re
from datetime import datetime

from app.domain.models import Appointment, AppointmentStatus

PROTECTED_ACTIONS = {"list_appointments", "confirm_appointment", "cancel_appointment"}
ORDINAL_WORDS = {
    "first": 0,
    "1st": 0,
    "second": 1,
    "2nd": 1,
    "third": 2,
    "3rd": 2,
}


def normalize_phone(value: str) -> str:
    return "".join(character for character in value if character.isdigit())


def normalize_name(value: str) -> str:
    return " ".join(part for part in value.strip().split())


def normalize_dob(value: str) -> str | None:
    cleaned = value.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(cleaned, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def is_help_request(message: str) -> bool:
    return any(word in message for word in ["help", "what can you do", "options"])


def requires_verification(action: str | None) -> bool:
    return action in PROTECTED_ACTIONS


def missing_verification_fields(state: dict) -> list[str]:
    missing = []
    if not state.get("provided_full_name"):
        missing.append("full_name")
    if not state.get("provided_phone"):
        missing.append("phone")
    if not state.get("provided_dob"):
        missing.append("dob")
    return missing


def extract_phone(message: str) -> str | None:
    digits = normalize_phone(message)
    if len(digits) >= 10:
        return digits
    return None


def extract_dob(message: str) -> str | None:
    direct_match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", message)
    if direct_match:
        return normalize_dob(direct_match.group(0))
    slash_match = re.search(r"\b\d{2}/\d{2}/\d{4}\b", message)
    if slash_match:
        return normalize_dob(slash_match.group(0))
    return None


def extract_full_name(message: str) -> str | None:
    lowered = message.lower()
    for marker in ["my name is", "i am", "i'm", "im"]:
        pattern = rf"{marker}\s+([A-Za-zÀ-ÿ]+(?:\s+[A-Za-zÀ-ÿ]+)+)"
        match = re.search(pattern, lowered)
        if match:
            return normalize_name(match.group(1)).title()

    cleaned = re.sub(r"[^A-Za-zÀ-ÿ\s]", " ", message)
    candidate = normalize_name(cleaned)
    if len(candidate.split()) >= 2:
        blocked_words = {"phone", "number", "birth", "date", "appointment", "appointments", "confirm", "cancel", "show", "list"}
        if any(word in blocked_words for word in {part.lower() for part in candidate.split()}):
            return None
        return candidate.title()
    return None


def extract_requested_action(message: str, state: dict) -> str:
    lowered = message.lower()
    if "cancel" in lowered:
        return "cancel_appointment"
    if "confirm" in lowered:
        return "confirm_appointment"
    if any(keyword in lowered for keyword in ["appointment", "appointments", "show", "see", "list"]):
        return "list_appointments"
    if is_help_request(lowered):
        return "help"
    if state.get("deferred_action"):
        return state["deferred_action"]
    return "unknown"


def extract_appointment_reference(message: str) -> str | None:
    lowered = message.lower()
    date_match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", lowered)
    if date_match:
        return date_match.group(0)

    for word, index in ORDINAL_WORDS.items():
        if word in lowered:
            return str(index)

    index_match = re.search(r"\b(\d+)\b", lowered)
    if index_match:
        return index_match.group(1)

    return None


def resolve_appointment_reference(reference: str | None, appointments: list[Appointment]) -> Appointment | None:
    if not reference:
        return None

    exact_matches = [appointment for appointment in appointments if appointment.id == reference]
    if exact_matches:
        return exact_matches[0]

    date_matches = [appointment for appointment in appointments if appointment.date == reference]
    if len(date_matches) == 1:
        return date_matches[0]
    if len(date_matches) > 1:
        return None

    if reference.isdigit():
        index = int(reference)
        if 0 <= index < len(appointments):
            return appointments[index]
        if 1 <= index <= len(appointments):
            return appointments[index - 1]

    return None


def appointment_is_owned_by_patient(appointment: Appointment | None, patient_id: str | None) -> bool:
    return bool(appointment and patient_id and appointment.patient_id == patient_id)


def can_confirm(appointment: Appointment) -> bool:
    return appointment.status == AppointmentStatus.SCHEDULED


def can_cancel(appointment: Appointment) -> bool:
    return appointment.status in {AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED}
