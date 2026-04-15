from __future__ import annotations

import re

from app.domain.actions import Action
from app.domain.models import Appointment, DateOfBirth, FullName, Phone

ORDINAL_WORDS = {
    "first": 1,
    "1st": 1,
    "second": 2,
    "2nd": 2,
    "third": 3,
    "3rd": 3,
}


def is_help_request(message: str) -> bool:
    return any(word in message for word in ["help", "what can you do", "options"])


def extract_phone(message: str) -> str | None:
    digits = "".join(character for character in message if character.isdigit())
    if len(digits) < 10:
        return None
    return Phone(digits).digits


def extract_dob(message: str) -> str | None:
    direct_match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", message)
    if direct_match:
        try:
            return DateOfBirth(direct_match.group(0)).value
        except ValueError:
            return None
    slash_match = re.search(r"\b\d{2}/\d{2}/\d{4}\b", message)
    if slash_match:
        try:
            return DateOfBirth(slash_match.group(0)).value
        except ValueError:
            return None
    return None


def extract_full_name(message: str) -> str | None:
    lowered = message.lower()
    for marker in ["my name is", "i am", "i'm", "im"]:
        pattern = rf"{marker}\s+([A-Za-zÀ-ÿ]+(?:\s+[A-Za-zÀ-ÿ]+)+)"
        match = re.search(pattern, lowered)
        if match:
            return FullName(match.group(1)).value

    cleaned = re.sub(r"[^A-Za-zÀ-ÿ\s]", " ", message)
    candidate = " ".join(part for part in cleaned.strip().split())
    if len(candidate.split()) < 2:
        return None
    blocked_words = {"phone", "number", "birth", "date", "appointment", "appointments", "confirm", "cancel", "show", "list"}
    if any(word in blocked_words for word in {part.lower() for part in candidate.split()}):
        return None
    return FullName(candidate).value


def extract_requested_action(message: str, state: dict) -> Action:
    lowered = message.lower()
    if "cancel" in lowered:
        return Action.CANCEL_APPOINTMENT
    if "confirm" in lowered:
        return Action.CONFIRM_APPOINTMENT
    if any(keyword in lowered for keyword in ["appointment", "appointments", "show", "see", "list"]):
        return Action.LIST_APPOINTMENTS
    if is_help_request(lowered):
        return Action.HELP
    deferred_action = state.get("turn", {}).get("deferred_action")
    if deferred_action:
        return Action(deferred_action)
    return Action.UNKNOWN


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
        if 1 <= index <= len(appointments):
            return appointments[index - 1]
        if index == 0 and appointments:
            return appointments[0]

    return None
