from __future__ import annotations

from app.application.contracts.public import ForgetRememberedIdentityResponseData
from app.domain.services import RememberedIdentityService


class ForgetRememberedIdentityUseCase:
    def __init__(self, identity_service: RememberedIdentityService):
        self.identity_service = identity_service

    def execute(self, remembered_identity_id: str) -> ForgetRememberedIdentityResponseData:
        return ForgetRememberedIdentityResponseData(
            cleared=self.identity_service.revoke_identity(remembered_identity_id)
        )
