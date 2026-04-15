from __future__ import annotations

from app.infrastructure.persistence.in_memory import (
    InMemoryAppointmentRepository,
    InMemoryPatientRepository,
    InMemoryRememberedIdentityRepository,
)
from app.infrastructure.session.in_memory import InMemorySessionStore
from app.infrastructure.workflow.in_memory_checkpoint import InMemoryCheckpointStore
from app.runtime_assembly.bundles import RepositoryBundle


def build_repositories() -> RepositoryBundle:
    return RepositoryBundle(
        patient_repository=InMemoryPatientRepository(),
        appointment_repository=InMemoryAppointmentRepository(),
        identity_repository=InMemoryRememberedIdentityRepository(),
        session_store=InMemorySessionStore(),
        checkpoint_store=InMemoryCheckpointStore(),
    )
