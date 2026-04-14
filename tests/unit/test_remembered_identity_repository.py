from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.domain.models import RememberedIdentity, RememberedIdentityStatus
from app.repositories.sqlite_identity import SQLiteRememberedIdentityRepository


def test_sqlite_identity_repository_round_trip(tmp_path):
    repository = SQLiteRememberedIdentityRepository(tmp_path / "remembered_identity.sqlite")
    identity = RememberedIdentity(
        remembered_identity_id="rid-1",
        patient_id="p1",
        display_name="Ana Silva",
        verification_fingerprint="fingerprint",
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(hours=24),
        revoked_at=None,
        status=RememberedIdentityStatus.ACTIVE,
    )

    repository.save(identity)
    restored = repository.get_by_id("rid-1")

    assert restored is not None
    assert restored.patient_id == "p1"
    assert restored.status == RememberedIdentityStatus.ACTIVE


def test_sqlite_identity_repository_revokes_identity(tmp_path):
    repository = SQLiteRememberedIdentityRepository(tmp_path / "remembered_identity.sqlite")
    identity = RememberedIdentity(
        remembered_identity_id="rid-2",
        patient_id="p1",
        display_name="Ana Silva",
        verification_fingerprint="fingerprint",
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(hours=24),
        revoked_at=None,
        status=RememberedIdentityStatus.ACTIVE,
    )

    repository.save(identity)
    assert repository.revoke("rid-2") is True

    restored = repository.get_by_id("rid-2")
    assert restored is not None
    assert restored.status == RememberedIdentityStatus.REVOKED
