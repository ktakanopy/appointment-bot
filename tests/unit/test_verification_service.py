from __future__ import annotations

import pytest

from app.domain.errors import RepositoryUnavailableError
from app.domain.services import VerificationService
from app.infrastructure.persistence.in_memory import InMemoryPatientRepository


def test_verification_service_returns_matching_patient():
    service = VerificationService(InMemoryPatientRepository())

    patient = service.verify_identity("Ana Silva", "11999998888", "1990-05-10")

    assert patient is not None
    assert patient.id == "p1"


def test_verification_service_returns_none_for_unknown_patient():
    service = VerificationService(InMemoryPatientRepository())

    patient = service.verify_identity("Unknown Person", "11999998888", "1990-05-10")

    assert patient is None


def test_verification_service_wraps_repository_failures():
    class BrokenRepository:
        def find_by_identity(self, full_name, phone, dob):
            raise RuntimeError("boom")

    service = VerificationService(BrokenRepository())

    with pytest.raises(RepositoryUnavailableError):
        service.verify_identity("Ana Silva", "11999998888", "1990-05-10")
