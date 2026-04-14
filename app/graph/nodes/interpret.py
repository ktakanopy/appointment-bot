from __future__ import annotations

from app.domain import policies
from app.graph.state import ConversationState
from app.observability import log_event


def make_interpret_node(logger, provider):
    def interpret(state: ConversationState) -> ConversationState:
        message = (state.get("incoming_message") or "").strip()
        provider_result = provider.interpret(message, state)
        requested_action = provider_result.requested_action
        provider_phone = policies.extract_phone(provider_result.phone) if provider_result.phone else None
        provider_dob = policies.normalize_dob(provider_result.dob) if provider_result.dob else None
        provider_full_name = policies.normalize_name(provider_result.full_name).title() if provider_result.full_name else None
        if state.get("provided_phone") is None and provider_phone:
            state["provided_phone"] = provider_phone
        if state.get("provided_dob") is None and provider_dob:
            state["provided_dob"] = provider_dob
        if state.get("provided_full_name") is None and provider_full_name:
            state["provided_full_name"] = provider_full_name
        if provider_result.appointment_reference:
            state["appointment_reference"] = provider_result.appointment_reference
        state["requested_action"] = requested_action
        if requested_action in policies.PROTECTED_ACTIONS and not state.get("verified"):
            state["deferred_action"] = requested_action

        if requested_action in {"confirm_appointment", "cancel_appointment"} and not state.get("appointment_reference"):
            state["appointment_reference"] = provider_result.appointment_reference
        else:
            if requested_action not in {"confirm_appointment", "cancel_appointment"}:
                state["appointment_reference"] = None

        state["missing_verification_fields"] = policies.missing_verification_fields(state)
        log_event(
            logger,
            "parse_intent_and_entities",
            state,
            appointment_reference=state.get("appointment_reference"),
        )
        return state

    return interpret
