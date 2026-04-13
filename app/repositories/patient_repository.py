from __future__ import annotations

from typing import Protocol

from app.domain.models import Patient


class PatientRepository(Protocol):
    def find_by_identity(self, full_name: str, phone: str, dob: str) -> Patient | None:
        ...
