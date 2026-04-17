from __future__ import annotations

import json
import logging
import re
import time
from contextlib import contextmanager
from typing import Any

from app.config import Settings


def build_tracer(settings: Settings) -> object | None:
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
    setattr(logger, "tracer", None)
    return logger


def get_eval_logger() -> logging.Logger:
    get_logger()
    logger = logging.getLogger("appointment_bot.eval")
    if getattr(logger, "_appointment_bot_eval_configured", False):
        return logger

    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.propagate = True
    setattr(logger, "human_readable_logs", True)
    setattr(logger, "suppress_logs", True)
    setattr(logger, "eval_scenario_id", None)
    setattr(logger, "eval_scenario_title", None)
    setattr(logger, "_appointment_bot_eval_configured", True)
    return logger


def set_eval_scenario(logger: logging.Logger, scenario_id: str | None, scenario_title: str | None) -> None:
    setattr(logger, "eval_scenario_id", scenario_id)
    setattr(logger, "eval_scenario_title", scenario_title)


def log_eval_event(logger: logging.Logger, message: str) -> None:
    if getattr(logger, "human_readable_logs", False):
        logger.info(_format_eval_message(logger, message))
        return
    logger.info(message)


def log_event(logger: logging.Logger, node: str, state: Any, **extra: object) -> None:
    verification = _as_mapping(_state_value(state, "verification"))
    turn = _as_mapping(_state_value(state, "turn"))
    appointments = _as_mapping(_state_value(state, "appointments"))
    payload = {
        "thread_id": _state_value(state, "thread_id"),
        "node": node,
        "requested_operation": turn.get("requested_operation"),
        "verified": verification.get("verified"),
        "verification_status": verification.get("verification_status"),
        "issue": turn.get("issue"),
        "appointment_reference": appointments.get("appointment_reference"),
        "appointment_count": len(appointments.get("listed_appointments", []) or []),
    }
    payload.update(extra)
    _emit_log(logger, payload)


def summarize_state_for_trace(state: Any) -> dict[str, Any]:
    verification = _as_mapping(_state_value(state, "verification"))
    turn = _as_mapping(_state_value(state, "turn"))
    appointments = _as_mapping(_state_value(state, "appointments"))
    messages = _state_value(state, "messages") or []
    return redact_trace_payload(
        {
            "thread_id": _state_value(state, "thread_id"),
            "messages": _serialize_trace_messages(messages),
            "verification": {
                "verified": verification.get("verified"),
                "verification_failures": verification.get("verification_failures"),
                "verification_status": verification.get("verification_status"),
                "patient_id": verification.get("patient_id"),
                "provided_full_name": verification.get("provided_full_name"),
                "provided_phone": verification.get("provided_phone"),
                "provided_dob": verification.get("provided_dob"),
            },
            "turn": {
                "requested_operation": turn.get("requested_operation"),
                "issue": turn.get("issue"),
                "operation_result": _summarize_operation_result(turn.get("operation_result")),
            },
            "appointments": {
                "appointment_reference": appointments.get("appointment_reference"),
                "listed_appointments": [
                    _summarize_appointment(appointment)
                    for appointment in (appointments.get("listed_appointments") or [])
                ],
            },
        }
    )


def record_node_trace(
    logger: logging.Logger,
    tracer,
    *,
    node: str,
    state_before: Any,
    state_after: Any,
    extra: dict[str, Any] | None = None,
) -> None:
    payload = {
        "thread_id": _state_value(state_after, "thread_id") or _state_value(state_before, "thread_id"),
        "node": node,
        "input": summarize_state_for_trace(state_before),
        "output": summarize_state_for_trace(state_after),
        "metadata": redact_trace_payload(extra or {}),
    }
    record_trace_event(logger, tracer, f"node.{node}", payload)


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
    _emit_log(logger, {"event": event_name, **safe_payload})
    if tracer is None:
        return
    try:
        trace_id = str(safe_payload.get("thread_id") or event_name)
        trace = tracer.trace(id=trace_id, name="appointment_bot", session_id=trace_id)
        trace.event(name=event_name, input=safe_payload)
    except Exception:
        _emit_log(logger, {"event": event_name, "trace_status": "unavailable"})


def record_provider_event(logger: logging.Logger, tracer, event_name: str, payload: dict) -> None:
    record_trace_event(logger, tracer, f"provider.{event_name}", payload)


def get_or_create_trace(tracer, thread_id: str | None):
    if tracer is None:
        return None
    trace_id = str(thread_id or "appointment-bot")
    return tracer.trace(id=trace_id, name="appointment_bot", session_id=trace_id)


@contextmanager
def trace_span(
    logger: logging.Logger,
    tracer,
    *,
    thread_id: str | None,
    name: str,
    input_payload: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
):
    trace = get_or_create_trace(tracer, thread_id)
    span = None
    started_at = time.perf_counter()
    safe_input = redact_trace_payload(input_payload or {})
    safe_metadata = redact_trace_payload(metadata or {})
    try:
        if trace is not None:
            span = trace.span(name=name, input=safe_input or None, metadata=safe_metadata or None)
        yield span
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        if span is not None:
            span.update(metadata={**safe_metadata, "duration_ms": duration_ms, "status": "ok"})
    except Exception as exc:
        if span is not None:
            span.update(
                level="ERROR",
                status_message=type(exc).__name__,
                metadata={**safe_metadata, "error_type": type(exc).__name__},
            )
        raise


@contextmanager
def trace_generation(
    logger: logging.Logger,
    tracer,
    *,
    thread_id: str | None,
    name: str,
    model: str,
    input_payload: dict[str, Any],
    metadata: dict[str, Any] | None = None,
):
    trace = get_or_create_trace(tracer, thread_id)
    generation = None
    started_at = time.perf_counter()
    safe_input = redact_trace_payload(input_payload)
    safe_metadata = redact_trace_payload(metadata or {})
    try:
        if trace is not None:
            generation = trace.generation(
                name=name,
                model=model,
                input=safe_input,
                metadata=safe_metadata or None,
            )
        yield generation
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        if generation is not None:
            generation.update(metadata={**safe_metadata, "duration_ms": duration_ms, "status": "ok"})
    except Exception as exc:
        if generation is not None:
            generation.update(
                level="ERROR",
                status_message=type(exc).__name__,
                metadata={**safe_metadata, "error_type": type(exc).__name__},
            )
        raise


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


def _state_value(state: Any, key: str) -> Any:
    if isinstance(state, dict):
        return state.get(key)
    return getattr(state, key, None)


def _as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return {}


def _emit_log(logger: logging.Logger, payload: dict[str, Any]) -> None:
    if getattr(logger, "suppress_logs", False):
        return
    if getattr(logger, "human_readable_logs", False):
        logger.info(_format_human_readable_log(payload))
        return
    logger.info(json.dumps(payload, ensure_ascii=True, default=str))


def _format_human_readable_log(payload: dict[str, Any]) -> str:
    event = payload.get("event")
    if event == "workflow.start":
        thread_id = payload.get("thread_id", "-")
        messages = payload.get("payload", {}).get("messages", [])
        last_message = messages[-1]["content"] if messages else ""
        return f"workflow.start thread={thread_id} user={last_message!r}"

    if event == "workflow.end":
        result = payload.get("result", {})
        verification = result.get("verification", {})
        turn = result.get("turn", {})
        appointments = result.get("appointments", {})
        appointment_count = len(appointments.get("listed_appointments", []))
        return (
            "workflow.end "
            f"thread={payload.get('thread_id', '-')} "
            f"op={turn.get('requested_operation', '-')} "
            f"verified={verification.get('verified', False)} "
            f"status={verification.get('verification_status', '-')} "
            f"issue={turn.get('issue', '-')} "
            f"appointments={appointment_count}"
        )

    if isinstance(event, str) and event.startswith("provider."):
        if payload.get("status") == "ok":
            return ""
        provider = payload.get("provider", "-")
        status = payload.get("status", "-")
        error_type = payload.get("error_type")
        suffix = f" error={error_type}" if error_type else ""
        return f"{event} provider={provider} status={status}{suffix}"

    node = payload.get("node")
    if node:
        extra_parts = []
        if payload.get("outcome") is not None:
            extra_parts.append(f"outcome={payload['outcome']}")
        if payload.get("appointment_reference") is not None:
            extra_parts.append(f"reference={payload['appointment_reference']}")
        if payload.get("appointment_count") is not None:
            extra_parts.append(f"appointments={payload['appointment_count']}")
        extra = f" {' '.join(extra_parts)}" if extra_parts else ""
        return (
            f"node={node} "
            f"op={payload.get('requested_operation', '-')} "
            f"verified={payload.get('verified', False)} "
            f"status={payload.get('verification_status', '-')} "
            f"issue={payload.get('issue', '-')}{extra}"
        )

    return json.dumps(payload, ensure_ascii=True, default=str)


def _serialize_trace_messages(messages: list[Any]) -> list[dict[str, str]]:
    serialized = []
    for message in messages:
        if isinstance(message, dict):
            serialized.append({
                "role": str(message.get("role", "assistant")),
                "content": str(message.get("content", "")),
            })
            continue
        role = getattr(message, "type", None) or getattr(message, "role", None) or "assistant"
        content = getattr(message, "content", "")
        serialized.append({"role": str(role), "content": str(content)})
    return serialized


def _summarize_operation_result(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    mapping = _as_mapping(value)
    if not mapping:
        return None
    return {
        "operation": mapping.get("operation"),
        "outcome": mapping.get("outcome"),
        "appointment_id": mapping.get("appointment_id"),
    }


def _summarize_appointment(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    mapping = _as_mapping(value)
    if not mapping:
        return None
    return {
        "id": mapping.get("id"),
        "date": mapping.get("date"),
        "time": mapping.get("time"),
        "doctor": mapping.get("doctor"),
        "status": mapping.get("status"),
    }


def _format_eval_message(logger: logging.Logger, message: str) -> str:
    scenario_id = getattr(logger, "eval_scenario_id", None)
    scenario_title = getattr(logger, "eval_scenario_title", None)
    if not scenario_id:
        return message
    title_suffix = f" ({scenario_title})" if scenario_title else ""
    return f"[{scenario_id}{title_suffix}] {message}"
