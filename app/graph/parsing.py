from __future__ import annotations

import re

from app.models import Appointment, ConversationOperation, DateOfBirth, FullName, Phone

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
    return Phone.try_parse(digits)


def extract_dob(message: str) -> str | None:
    direct_match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", message)
    if direct_match:
        return DateOfBirth.try_parse(direct_match.group(0))
    slash_match = re.search(r"\b\d{2}/\d{2}/\d{4}\b", message)
    if slash_match:
        return DateOfBirth.try_parse(slash_match.group(0))
    return None


def extract_full_name(message: str) -> str | None:
    lowered = message.lower()
    for marker in ["my name is", "i am", "i'm", "im"]:
        pattern = rf"{marker}\s+([A-Za-zÀ-ÿ]+(?:\s+[A-Za-zÀ-ÿ]+)+)"
        match = re.search(pattern, lowered)
        if match:
            return FullName.try_parse(match.group(1))

    cleaned = re.sub(r"[^A-Za-zÀ-ÿ\s]", " ", message)
    candidate = " ".join(part for part in cleaned.strip().split())
    if len(candidate.split()) < 2:
        return None
    blocked_words = {"phone", "number", "birth", "date", "appointment", "appointments", "confirm", "cancel", "show", "list"}
    if any(word in blocked_words for word in {part.lower() for part in candidate.split()}):
        return None
    return FullName.try_parse(candidate)


def extract_requested_operation(message: str, state: dict) -> ConversationOperation:
    lowered = message.lower()
    if "cancel" in lowered:
        return ConversationOperation.CANCEL_APPOINTMENT
    if "confirm" in lowered:
        return ConversationOperation.CONFIRM_APPOINTMENT
    if any(keyword in lowered for keyword in ["appointment", "appointments", "show", "see", "list"]):
        return ConversationOperation.LIST_APPOINTMENTS
    if is_help_request(lowered):
        return ConversationOperation.HELP
    return ConversationOperation.UNKNOWN


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
    """Map a loose user reference string to a single appointment from the given list.

    Resolution order: match by appointment id; else if the string equals a date
    string and exactly one appointment has that date; else if the string is
    numeric, treat it as a 1-based index into appointments (1 is first), with 0
    accepted as an alias for the first item when the list is non-empty.

    Returns None when reference is empty or falsy, when more than one appointment
    shares the matched date, or when no rule produces a unique appointment.
    """
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
