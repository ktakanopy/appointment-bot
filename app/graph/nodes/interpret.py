from __future__ import annotations

from app.domain import policies
from app.graph.state import ConversationState
from app.observability import log_event

APPOINTMENT_ACTIONS = {"confirm_appointment", "cancel_appointment"}


def make_interpret_node(logger, provider):
    """Build the node that extracts intent and structured entities from a turn."""

    def interpret(state: ConversationState) -> ConversationState:
        message = (state.get("incoming_message") or "").strip()
        provider_state = dict(state)
        provider_state["missing_verification_fields"] = policies.missing_verification_fields(state)
        result = provider.interpret(message, provider_state)
        requested_action = result.requested_action

        _fill_missing_identity_fields(
            state,
            phone=policies.extract_phone(result.phone) if result.phone else None,
            dob=policies.normalize_dob(result.dob) if result.dob else None,
            full_name=policies.normalize_name(result.full_name).title() if result.full_name else None,
        )

        state["requested_action"] = requested_action
        _update_deferred_action(state, requested_action)
        _update_appointment_reference(state, requested_action, result.appointment_reference)
        log_event(
            logger,
            "parse_intent_and_entities",
            state,
            appointment_reference=state.get("appointment_reference"),
        )
        return state

    return interpret


def _fill_missing_identity_fields(
    state: ConversationState,
    *,
    phone: str | None,
    dob: str | None,
    full_name: str | None,
) -> None:
    """Persist newly extracted identity fields without overwriting prior inputs."""
    if state.get("provided_phone") is None and phone:
        state["provided_phone"] = phone
    if state.get("provided_dob") is None and dob:
        state["provided_dob"] = dob
    if state.get("provided_full_name") is None and full_name:
        state["provided_full_name"] = full_name


def _update_deferred_action(state: ConversationState, requested_action: str) -> None:
    """Remember protected actions until verification completes."""
    if requested_action in policies.PROTECTED_ACTIONS and not state.get("verified"):
        state["deferred_action"] = requested_action


def _update_appointment_reference(
    state: ConversationState,
    requested_action: str,
    appointment_reference: str | None,
) -> None:
    """Keep appointment references only for confirm and cancel flows."""
    if requested_action not in APPOINTMENT_ACTIONS:
        state["appointment_reference"] = None
        return
    if state.get("appointment_reference") is None and appointment_reference:
        state["appointment_reference"] = appointment_reference
