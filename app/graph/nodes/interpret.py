from __future__ import annotations

from app.domain import parsing, policies
from app.graph.state import AppointmentState, ConversationState, TurnState, appointment_state, turn_state, verification_state
from app.observability import log_event

APPOINTMENT_ACTIONS = {"confirm_appointment", "cancel_appointment"}


def make_interpret_node(logger, provider):
    def interpret(state: ConversationState) -> ConversationState:
        message = (state.incoming_message or "").strip()
        verification = verification_state(state)
        turn = turn_state(state)
        appointments = appointment_state(state)
        provider_state = {
            "verification": {"verified": verification.verified},
            "turn": {
                "requested_action": turn.requested_action,
                "deferred_action": turn.deferred_action,
            },
            "missing_verification_fields": verification.missing_fields(),
        }
        result = provider.interpret(message, provider_state)
        requested_action = result.requested_action

        verification.fill_missing_fields(
            phone=parsing.extract_phone(result.phone) if result.phone else None,
            dob=parsing.normalize_dob(result.dob) if result.dob else None,
            full_name=parsing.normalize_name(result.full_name).title() if result.full_name else None,
        )

        turn.requested_action = requested_action
        _update_deferred_action(verification, turn, requested_action)
        _update_appointment_reference(appointments, requested_action, result.appointment_reference)
        log_event(
            logger,
            "parse_intent_and_entities",
            state,
            appointment_reference=appointments.appointment_reference,
        )
        return state

    return interpret


def _update_deferred_action(verification: VerificationState, turn: TurnState, requested_action: str) -> None:
    if requested_action in policies.PROTECTED_ACTIONS and not verification.verified:
        turn.deferred_action = requested_action


def _update_appointment_reference(
    appointments: AppointmentState,
    requested_action: str,
    appointment_reference: str | None,
) -> None:
    if requested_action not in APPOINTMENT_ACTIONS:
        appointments.appointment_reference = None
        return
    if appointments.appointment_reference is None and appointment_reference:
        appointments.appointment_reference = appointment_reference
