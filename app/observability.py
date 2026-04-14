from __future__ import annotations

import json
import logging
import re


def build_tracer(settings):
    if not settings.tracing.enabled:
        return None
    if not settings.tracing.public_key or not settings.tracing.secret_key:
        return None
    try:
        from langfuse import Langfuse

        return Langfuse(
            public_key=settings.tracing.public_key,
            secret_key=settings.tracing.secret_key,
            host=settings.tracing.host,
        )
    except Exception:
        return None


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


def redact_trace_payload(payload: dict) -> dict:
    redacted = {}
    for key, value in payload.items():
        if key in {"provided_full_name", "display_name"} and value:
            redacted[key] = "[redacted-name]"
            continue
        if key in {"provided_phone", "phone"} and value:
            redacted[key] = _redact_phone(str(value))
            continue
        if key in {"provided_dob", "dob"} and value:
            redacted[key] = "[redacted-dob]"
            continue
        if key == "messages" and isinstance(value, list):
            redacted[key] = [{"role": item.get("role"), "content": _redact_message(item.get("content"))} for item in value]
            continue
        if isinstance(value, dict):
            redacted[key] = redact_trace_payload(value)
            continue
        redacted[key] = value
    return redacted


def record_trace_event(logger: logging.Logger, tracer, event_name: str, payload: dict) -> None:
    safe_payload = redact_trace_payload(payload)
    logger.info(json.dumps({"event": event_name, **safe_payload}, ensure_ascii=True, default=str))
    if tracer is None:
        return
    try:
        tracer.create_event(name=event_name, body=safe_payload)
    except Exception:
        logger.info(json.dumps({"event": event_name, "trace_status": "unavailable"}, ensure_ascii=True))


def record_provider_event(logger: logging.Logger, tracer, event_name: str, payload: dict) -> None:
    record_trace_event(logger, tracer, f"provider.{event_name}", payload)


def _redact_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) < 4:
        return "[redacted-phone]"
    return f"[redacted-phone-{digits[-4:]}]"


def _redact_message(value: str | None) -> str | None:
    if value is None:
        return None
    result = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "[redacted-dob]", value)
    result = re.sub(r"\b\d{2}/\d{2}/\d{4}\b", "[redacted-dob]", result)
    result = re.sub(r"\b\d{10,}\b", "[redacted-phone]", result)
    return result
