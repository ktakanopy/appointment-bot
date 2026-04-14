from __future__ import annotations

from typing import Protocol

from app.domain.models import RememberedIdentity


class RememberedIdentityRepository(Protocol):
    def get_by_id(self, remembered_identity_id: str) -> RememberedIdentity | None:
        ...

    def get_active_by_patient_id(self, patient_id: str) -> RememberedIdentity | None:
        ...

    def save(self, identity: RememberedIdentity) -> RememberedIdentity:
        ...

    def revoke(self, remembered_identity_id: str) -> bool:
        ...
