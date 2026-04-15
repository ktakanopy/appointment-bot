from __future__ import annotations

import logging
from collections.abc import Callable

from app.application.services.chat_response_service import ChatResponseService
from app.application.services.response_policy import ResponsePolicy
from app.application.session_service import SessionService
from app.config import Settings
from app.domain.services import AppointmentService, RememberedIdentityService, VerificationService
from app.runtime_assembly.bundles import RepositoryBundle, ServiceBundle


def build_services(
    *,
    settings: Settings,
    logger: logging.Logger,
    tracer: object | None,
    repositories: RepositoryBundle,
    provider_factory: Callable[..., object],
) -> ServiceBundle:
    provider = provider_factory(settings, logger, tracer=tracer)
    verification_service = VerificationService(repositories.patient_repository)
    appointment_service = AppointmentService(repositories.appointment_repository)
    identity_service = RememberedIdentityService(identity_repository=repositories.identity_repository, ttl_hours=settings.remembered_identity_ttl_hours)
    session_service = SessionService(repositories.session_store, settings.session_ttl_minutes)
    response_service = ChatResponseService(response_policy=ResponsePolicy())
    return ServiceBundle(
        provider=provider,
        verification_service=verification_service,
        appointment_service=appointment_service,
        identity_service=identity_service,
        session_service=session_service,
        response_service=response_service,
    )
