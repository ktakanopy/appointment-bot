from __future__ import annotations

import time
from typing import Any

from app.application.session_service import SessionBootstrap, SessionService
from app.domain.actions import Action
from app.domain.models import RememberedIdentity
from app.domain.services import RememberedIdentityService


class ChatService:
    def __init__(self, identity_service: RememberedIdentityService, session_service: SessionService):
        self.identity_service = identity_service
        self.session_service = session_service

    def build_payload(self, session_id: str, message: str, remembered_identity_id: str | None = None) -> dict[str, Any]:
        self.session_service.cleanup_expired()
        session = self.session_service.require_session(session_id)
        if remembered_identity_id:
            session.remembered_identity_id = remembered_identity_id
        bootstrap = session.bootstrap
        session.bootstrap = None
        if bootstrap is None and remembered_identity_id:
            restored_identity = self.identity_service.restore_identity(remembered_identity_id)
            bootstrap = SessionBootstrap(
                state=self.session_service.build_bootstrap_state(restored_identity),
                created_at=time.monotonic(),
            )
        payload = {"thread_id": session_id, "incoming_message": message}
        if bootstrap:
            payload.update(bootstrap.state)
        return payload

    def build_response(
        self,
        session_id: str,
        remembered_identity_id: str | None,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        session = self.session_service.require_session(session_id)
        verification = result.get("verification")
        turn = result.get("turn")
        appointments_state = result.get("appointments")
        appointments = None
        listed_appointments = _section_value(appointments_state, "listed_appointments", [])
        if _section_value(turn, "requested_action") == Action.LIST_APPOINTMENTS.value and listed_appointments:
            appointments = [
                {
                    "id": appointment.id,
                    "date": appointment.date,
                    "time": appointment.time,
                    "doctor": appointment.doctor,
                    "status": appointment.status.value,
                }
                for appointment in listed_appointments
            ]

        last_action_result = None
        if _section_value(turn, "last_action_result"):
            last_action_result = dict(_section_value(turn, "last_action_result"))

        remembered_identity = self.ensure_remembered_identity(session, remembered_identity_id, result)
        remembered_identity_status = self.session_service.build_identity_summary(
            remembered_identity,
            remembered_identity_id or session.remembered_identity_id,
        )

        current_action = _section_value(turn, "requested_action", Action.UNKNOWN.value) or Action.UNKNOWN.value
        if not _section_value(verification, "verified", False) and current_action in {
            Action.UNKNOWN.value,
            Action.HELP.value,
            Action.VERIFY_IDENTITY.value,
        }:
            current_action = Action.VERIFY_IDENTITY.value

        return {
            "response": _section_value(turn, "response_text"),
            "verified": _section_value(verification, "verified", False),
            "current_action": current_action,
            "thread_id": session_id,
            "appointments": appointments,
            "last_action_result": last_action_result,
            "error_code": _section_value(turn, "error_code"),
            "remembered_identity_status": remembered_identity_status,
        }

    def ensure_remembered_identity(
        self,
        session,
        requested_identity_id: str | None,
        result: dict[str, Any],
    ) -> RememberedIdentity | None:
        verification = result.get("verification")
        if not _section_value(verification, "verified", False) or not _section_value(verification, "patient_id"):
            identity_id = requested_identity_id or session.remembered_identity_id
            identity = self.identity_service.restore_identity(identity_id)
            if identity is not None:
                session.remembered_identity_id = identity.remembered_identity_id
            return identity
        fingerprint = self.identity_service.build_fingerprint(
            _section_value(verification, "provided_full_name"),
            _section_value(verification, "provided_phone"),
            _section_value(verification, "provided_dob"),
            _section_value(verification, "patient_id"),
        )
        identity = self.identity_service.ensure_identity(
            patient_id=_section_value(verification, "patient_id"),
            display_name=_section_value(verification, "provided_full_name"),
            verification_fingerprint=fingerprint,
        )
        session.remembered_identity_id = identity.remembered_identity_id
        return identity


def _section_value(section: Any, key: str, default: Any = None) -> Any:
    if isinstance(section, dict):
        return section.get(key, default)
    if section is None:
        return default
    return getattr(section, key, default)
