from __future__ import annotations

import re

from app.models import ConversationOperation, DateOfBirth, FullName, Phone


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

    # Fallback for short identity replies such as "Ana Silva" during the
    # verification flow when the user does not include any explicit marker.
    cleaned = re.sub(r"[^A-Za-zÀ-ÿ\s]", " ", message)
    candidate = " ".join(part for part in cleaned.strip().split())
    if len(candidate.split()) < 2:
        return None
    blocked_words = {
        "phone",
        "number",
        "birth",
        "date",
        "appointment",
        "appointments",
        "confirm",
        "cancel",
        "show",
        "list",
    }
    if any(
        word in blocked_words for word in {part.lower() for part in candidate.split()}
    ):
        return None
    return FullName.try_parse(candidate)


def extract_requested_operation(message: str, state: dict) -> ConversationOperation:
    lowered = message.lower()
    if "cancel" in lowered:
        return ConversationOperation.CANCEL_APPOINTMENT
    if "confirm" in lowered:
        return ConversationOperation.CONFIRM_APPOINTMENT
    if any(
        keyword in lowered
        for keyword in ["appointment", "appointments", "show", "see", "list"]
    ):
        return ConversationOperation.LIST_APPOINTMENTS
    if is_help_request(lowered):
        return ConversationOperation.HELP
    return ConversationOperation.UNKNOWN
