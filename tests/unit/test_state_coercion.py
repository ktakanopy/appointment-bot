"""Regression tests for appointment_state() deserialization.

LangGraph stores node output via model_dump(), so listed_appointments is
persisted as a list of plain dicts between turns. appointment_state() must
coerce those dicts back to Appointment objects before any node reads .id,
.date, or .status. If that coercion breaks, index resolution crashes with
AttributeError: 'dict' object has no attribute 'id'.
"""
from __future__ import annotations

from app.graph.state import appointment_state
from app.models import Appointment, AppointmentStatus


SERIALIZED_STATE = {
    "appointments": {
        "listed_appointments": [
            {
                "id": "a1",
                "patient_id": "p1",
                "date": "2026-04-20",
                "time": "14:00",
                "doctor": "Dr. Costa",
                "status": "scheduled",
            },
            {
                "id": "a2",
                "patient_id": "p1",
                "date": "2026-04-23",
                "time": "09:30",
                "doctor": "Dr. Lima",
                "status": "confirmed",
            },
        ],
        "selected_index": 2,
    }
}


def test_appointment_state_coerces_dicts_to_appointment_objects():
    """Dicts stored by model_dump() must come back as Appointment instances."""
    state = appointment_state(SERIALIZED_STATE)

    assert len(state.listed_appointments) == 2
    for appt in state.listed_appointments:
        assert isinstance(appt, Appointment), (
            f"Expected Appointment, got {type(appt).__name__}. "
            "If this fails, index resolution will crash with AttributeError."
        )


def test_appointment_state_preserves_field_values_after_coercion():
    state = appointment_state(SERIALIZED_STATE)

    first = state.listed_appointments[0]
    assert first.id == "a1"
    assert first.patient_id == "p1"
    assert first.date == "2026-04-20"
    assert first.time == "14:00"
    assert first.doctor == "Dr. Costa"
    assert first.status == AppointmentStatus.SCHEDULED

    second = state.listed_appointments[1]
    assert second.id == "a2"
    assert second.status == AppointmentStatus.CONFIRMED


def test_appointment_state_preserves_selected_index():
    state = appointment_state(SERIALIZED_STATE)

    assert state.selected_index == 2


def test_appointment_state_returns_empty_list_when_appointments_key_missing():
    state = appointment_state({})

    assert state.listed_appointments == []
    assert state.selected_index is None


def test_appointment_state_handles_empty_listed_appointments():
    state = appointment_state({"appointments": {"listed_appointments": []}})

    assert state.listed_appointments == []
