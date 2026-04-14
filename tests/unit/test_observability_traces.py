from __future__ import annotations

import logging

from app.observability import record_trace_event, redact_trace_payload


def test_redact_trace_payload_masks_identity_fields():
    payload = redact_trace_payload(
        {
            "provided_full_name": "Ana Silva",
            "provided_phone": "11999998888",
            "provided_dob": "1990-05-10",
            "messages": [{"role": "user", "content": "My phone is 11999998888 and dob is 1990-05-10"}],
        }
    )

    assert payload["provided_full_name"] == "[redacted-name]"
    assert payload["provided_phone"].startswith("[redacted-phone-")
    assert payload["provided_dob"] == "[redacted-dob]"
    assert "[redacted-phone]" in payload["messages"][0]["content"]


def test_record_trace_event_does_not_raise_when_tracer_fails(caplog):
    class BrokenTracer:
        def create_event(self, **kwargs):
            raise RuntimeError("trace down")

    record_trace_event(
        logger=logging.getLogger("appointment_bot"),
        tracer=BrokenTracer(),
        event_name="workflow.test",
        payload={"provided_phone": "11999998888"},
    )
