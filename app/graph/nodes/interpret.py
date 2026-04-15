from __future__ import annotations

from app.application.contracts.conversation import ConversationOperation
from app.domain.models import DateOfBirth, FullName
from app.graph.state import (
    AppointmentState,
    ConversationState,
    TurnState,
    VerificationState,
    appointment_state,
    turn_state,
    verification_state,
)
from app.graph.text_extraction import extract_phone
from app.observability import log_event

APPOINTMENT_ACTIONS = {
    ConversationOperation.CONFIRM_APPOINTMENT,
    ConversationOperation.CANCEL_APPOINTMENT,
}


def make_interpret_node(logger, provider):
    def interpret(state: ConversationState) -> ConversationState:
        message = (state.incoming_message or "").strip()
        verification = verification_state(state)
        turn = turn_state(state)
        appointments = appointment_state(state)
        provider_state = {
            "verification": {"verified": verification.verified},
            "turn": {
                "requested_operation": turn.requested_operation.value,
                "deferred_operation": (
                    turn.deferred_operation.value if turn.deferred_operation is not None else None
                ),
            },
            "missing_verification_fields": verification.missing_fields(),
        }
        result = provider.interpret(message, provider_state)
        requested_operation = result.requested_operation

        verification.fill_missing_fields(
            phone=_normalize_phone(result.phone),
            dob=_normalize_dob(result.dob),
            full_name=_normalize_full_name(result.full_name),
        )

        turn.requested_operation = requested_operation
        _update_deferred_operation(verification, turn, requested_operation)
        _update_appointment_reference(appointments, requested_operation, result.appointment_reference)
        log_event(
            logger,
            "parse_intent_and_entities",
            state,
            appointment_reference=appointments.appointment_reference,
        )
        return state

    return interpret


def _update_deferred_operation(
    verification: VerificationState,
    turn: TurnState,
    requested_operation: ConversationOperation,
) -> None:
    if requested_operation.requires_verification and not verification.verified:
        turn.deferred_operation = requested_operation


def _update_appointment_reference(
    appointments: AppointmentState,
    requested_operation: ConversationOperation,
    appointment_reference: str | None,
) -> None:
    if requested_operation not in APPOINTMENT_ACTIONS:
        appointments.appointment_reference = None
        return
    if appointments.appointment_reference is None and appointment_reference:
        appointments.appointment_reference = appointment_reference


def _normalize_full_name(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return FullName(value).value
    except ValueError:
        return None


def _normalize_phone(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return extract_phone(value)
    except ValueError:
        return None


def _normalize_dob(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return DateOfBirth(value).value
    except ValueError:
        return None
