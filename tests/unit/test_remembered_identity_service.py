from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.domain.models import RememberedIdentity, RememberedIdentityStatus
from app.domain.services import RememberedIdentityService


class FakeRepository:
    def __init__(self):
        self.by_id = {}

    def get_by_id(self, remembered_identity_id):
        return self.by_id.get(remembered_identity_id)

    def get_active_by_patient_id(self, patient_id):
        for identity in self.by_id.values():
            if identity.patient_id == patient_id:
                return identity
        return None

    def save(self, identity):
        self.by_id[identity.remembered_identity_id] = identity
        return identity

    def revoke(self, remembered_identity_id):
        identity = self.by_id.get(remembered_identity_id)
        if identity is None:
            return False
        self.by_id[remembered_identity_id] = RememberedIdentity(
            remembered_identity_id=identity.remembered_identity_id,
            patient_id=identity.patient_id,
            display_name=identity.display_name,
            verification_fingerprint=identity.verification_fingerprint,
            issued_at=identity.issued_at,
            expires_at=identity.expires_at,
            revoked_at=datetime.now(UTC),
            status=RememberedIdentityStatus.REVOKED,
        )
        return True


def test_remembered_identity_service_reuses_active_identity():
    repository = FakeRepository()
    service = RememberedIdentityService(repository, ttl_hours=24, now_factory=lambda: datetime(2026, 4, 13, tzinfo=UTC))

    first = service.ensure_identity("p1", "Ana Silva", "fingerprint")
    second = service.ensure_identity("p1", "Ana Silva", "fingerprint")

    assert first.remembered_identity_id == second.remembered_identity_id


def test_remembered_identity_service_marks_expired_identity():
    now = datetime(2026, 4, 13, tzinfo=UTC)
    repository = FakeRepository()
    repository.save(
        RememberedIdentity(
            remembered_identity_id="rid-1",
            patient_id="p1",
            display_name="Ana Silva",
            verification_fingerprint="fingerprint",
            issued_at=now - timedelta(hours=48),
            expires_at=now - timedelta(hours=1),
            revoked_at=None,
            status=RememberedIdentityStatus.ACTIVE,
        )
    )
    service = RememberedIdentityService(repository, ttl_hours=24, now_factory=lambda: now)

    restored = service.restore_identity("rid-1")

    assert restored is not None
    assert restored.status == RememberedIdentityStatus.EXPIRED
