from __future__ import annotations

from app.application.contracts.public import RememberedIdentitySummary
from app.domain.models import RememberedIdentity


class IdentityPresenter:
    def present(
        self,
        identity: RememberedIdentity | None,
        requested_identity_id: str | None = None,
    ) -> RememberedIdentitySummary:
        if identity is None:
            return RememberedIdentitySummary(
                remembered_identity_id=requested_identity_id or "",
                status="unavailable",
                display_name=None,
                expires_at=None,
            )
        return RememberedIdentitySummary(
            remembered_identity_id=identity.remembered_identity_id,
            status=identity.status.value,
            display_name=identity.display_name,
            expires_at=identity.expires_at.isoformat(),
        )
