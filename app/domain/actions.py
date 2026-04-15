from __future__ import annotations

from enum import Enum


class Action(str, Enum):
    VERIFY_IDENTITY = "verify_identity"
    LIST_APPOINTMENTS = "list_appointments"
    CONFIRM_APPOINTMENT = "confirm_appointment"
    CANCEL_APPOINTMENT = "cancel_appointment"
    HELP = "help"
    UNKNOWN = "unknown"

    @property
    def requires_verification(self) -> bool:
        return self in {
            Action.LIST_APPOINTMENTS,
            Action.CONFIRM_APPOINTMENT,
            Action.CANCEL_APPOINTMENT,
        }

    @property
    def is_appointment_mutation(self) -> bool:
        return self in {Action.CONFIRM_APPOINTMENT, Action.CANCEL_APPOINTMENT}

    @property
    def triggers_verification_flow(self) -> bool:
        return self in {Action.HELP, Action.UNKNOWN, Action.VERIFY_IDENTITY}
