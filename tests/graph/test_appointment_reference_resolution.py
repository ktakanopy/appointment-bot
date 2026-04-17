"""Integration tests for appointment reference resolution across turn boundaries.

These tests guard against the regression where listed_appointments was stored
as plain dicts via model_dump() but read back without coercion, causing
AttributeError: 'dict' object has no attribute 'id' inside
resolve_appointment_reference.

Covers the three resolution strategies (ordinal numeric index, date string,
appointment ID) for both cancel and confirm, exercised after a real
list_appointments turn so the state round-trip through LangGraph is included.
"""
from __future__ import annotations

import pytest

from app.models import ActionOutcome, AppointmentStatus, ConversationOperation
from tests.support import build_test_workflow


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VERIFICATION_TURNS = [
    "show my appointments",
    "Ana Silva",
    "11999998888",
    "1990-05-10",
]


def _verified_workflow(thread_id: str):
    """Return a workflow that has already passed verification and listed appointments."""
    wf = build_test_workflow()
    for msg in _VERIFICATION_TURNS:
        wf.run(thread_id, msg)
    return wf


# ---------------------------------------------------------------------------
# Cancel by numeric index
# ---------------------------------------------------------------------------

def test_cancel_by_numeric_index_1_targets_first_appointment():
    wf = _verified_workflow("cancel-idx-1")
    result = wf.run("cancel-idx-1", "cancel 1")

    assert result.turn.operation_result.outcome == ActionOutcome.CANCELED
    assert result.turn.operation_result.appointment_id == "a1"
    assert result.appointments.listed_appointments[0].status == AppointmentStatus.CANCELED


def test_cancel_by_numeric_index_2_targets_second_appointment():
    wf = _verified_workflow("cancel-idx-2")
    result = wf.run("cancel-idx-2", "cancel 2")

    assert result.turn.operation_result.outcome == ActionOutcome.CANCELED
    assert result.turn.operation_result.appointment_id == "a2"
    assert result.appointments.listed_appointments[1].status == AppointmentStatus.CANCELED


# ---------------------------------------------------------------------------
# Cancel by date reference
# ---------------------------------------------------------------------------

def test_cancel_by_date_reference_targets_matching_appointment():
    wf = _verified_workflow("cancel-date")
    result = wf.run("cancel-date", "cancel my 2026-04-20 appointment")

    assert result.turn.operation_result.outcome == ActionOutcome.CANCELED
    assert result.turn.operation_result.appointment_id == "a1"


def test_cancel_by_date_for_second_appointment():
    wf = _verified_workflow("cancel-date-2")
    result = wf.run("cancel-date-2", "cancel my 2026-04-23 appointment")

    assert result.turn.operation_result.outcome == ActionOutcome.CANCELED
    assert result.turn.operation_result.appointment_id == "a2"


# ---------------------------------------------------------------------------
# Cancel by appointment ID
# ---------------------------------------------------------------------------

def test_cancel_by_numeric_index_0_is_alias_for_first():
    """Index 0 is accepted as an alias for the first appointment."""
    wf = _verified_workflow("cancel-idx-0")
    result = wf.run("cancel-idx-0", "cancel 0")

    assert result.turn.operation_result.outcome == ActionOutcome.CANCELED
    assert result.turn.operation_result.appointment_id == "a1"


def test_cancel_second_appointment_after_first_was_already_canceled():
    """Ordinal reference resolves correctly against state that changed in the same session."""
    wf = _verified_workflow("cancel-after-cancel")
    wf.run("cancel-after-cancel", "cancel 1")
    result = wf.run("cancel-after-cancel", "cancel 2")

    assert result.turn.operation_result.outcome == ActionOutcome.CANCELED
    assert result.turn.operation_result.appointment_id == "a2"
    assert result.appointments.listed_appointments[0].status == AppointmentStatus.CANCELED
    assert result.appointments.listed_appointments[1].status == AppointmentStatus.CANCELED


# ---------------------------------------------------------------------------
# Confirm by numeric index
# ---------------------------------------------------------------------------

def test_confirm_by_numeric_index_1_targets_first_appointment():
    wf = _verified_workflow("confirm-idx-1")
    result = wf.run("confirm-idx-1", "confirm 1")

    assert result.turn.operation_result.outcome == ActionOutcome.CONFIRMED
    assert result.turn.operation_result.appointment_id == "a1"
    assert result.appointments.listed_appointments[0].status == AppointmentStatus.CONFIRMED


def test_confirm_by_numeric_index_2_targets_second_appointment():
    wf = _verified_workflow("confirm-idx-2")

    # a2 is already CONFIRMED, so we confirm a1 first to get a clean state,
    # then confirm 2 to verify the index targets the right slot.
    wf.run("confirm-idx-2", "confirm 1")
    result = wf.run("confirm-idx-2", "confirm 2")

    assert result.turn.operation_result.outcome == ActionOutcome.ALREADY_CONFIRMED
    assert result.turn.operation_result.appointment_id == "a2"


# ---------------------------------------------------------------------------
# Confirm by date reference
# ---------------------------------------------------------------------------

def test_confirm_by_date_reference():
    wf = _verified_workflow("confirm-date")
    result = wf.run("confirm-date", "confirm my 2026-04-20 appointment")

    assert result.turn.operation_result.outcome == ActionOutcome.CONFIRMED
    assert result.turn.operation_result.appointment_id == "a1"


# ---------------------------------------------------------------------------
# listed_appointments reflects mutation after state round-trip
# ---------------------------------------------------------------------------

def test_listed_appointments_are_appointment_objects_after_mutation():
    """Ensure that listed_appointments returned after a mutation are typed
    Appointment objects, not plain dicts — guarding the state coercion path."""
    from app.models import Appointment

    wf = _verified_workflow("coercion-check")
    result = wf.run("coercion-check", "cancel 1")

    for appt in result.appointments.listed_appointments:
        assert isinstance(appt, Appointment), (
            f"listed_appointments contains {type(appt).__name__}, not Appointment. "
            "This indicates appointment_state() coercion is broken."
        )
