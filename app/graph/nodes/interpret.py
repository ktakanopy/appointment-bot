from __future__ import annotations

from app.domain import policies
from app.graph.state import AppointmentState, ConversationState, TurnState, VerificationState, appointment_state, turn_state, verification_state
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
            "missing_verification_fields": policies.missing_verification_fields(state),
        }
        result = provider.interpret(message, provider_state)
        requested_action = result.requested_action

        _fill_missing_identity_fields(
            verification,
            phone=policies.extract_phone(result.phone) if result.phone else None,
            dob=policies.normalize_dob(result.dob) if result.dob else None,
            full_name=policies.normalize_name(result.full_name).title() if result.full_name else None,
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


def _fill_missing_identity_fields(
    verification: VerificationState,
    *,
    phone: str | None,
    dob: str | None,
    full_name: str | None,
) -> None:
    if verification.provided_phone is None and phone:
        verification.provided_phone = phone
    if verification.provided_dob is None and dob:
        verification.provided_dob = dob
    if verification.provided_full_name is None and full_name:
        verification.provided_full_name = full_name


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
