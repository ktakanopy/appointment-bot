from __future__ import annotations

from app.domain.models import DateOfBirth, FullName
from app.graph.text_extraction import extract_phone


def normalize_full_name(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return FullName(value).value
    except ValueError:
        return None


def normalize_phone(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return extract_phone(value)
    except ValueError:
        return None


def normalize_dob(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return DateOfBirth(value).value
    except ValueError:
        return None
