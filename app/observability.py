from __future__ import annotations

import json
import logging


def get_logger() -> logging.Logger:
    logger = logging.getLogger("appointment_bot")
    if logger.handlers:
        return logger

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


def log_event(logger: logging.Logger, node: str, state: dict, **extra: object) -> None:
    payload = {
        "thread_id": state.get("thread_id"),
        "node": node,
        "requested_action": state.get("requested_action"),
        "verified": state.get("verified"),
        "verification_status": state.get("verification_status"),
        "error_code": state.get("error_code"),
    }
    payload.update(extra)
    logger.info(json.dumps(payload, ensure_ascii=True, default=str))
