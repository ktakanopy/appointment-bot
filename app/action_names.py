from __future__ import annotations

from typing import Literal

ActionName = Literal[
    "verify_identity",
    "list_appointments",
    "confirm_appointment",
    "cancel_appointment",
    "help",
    "unknown",
]
