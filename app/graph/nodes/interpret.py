from __future__ import annotations

from app.domain import policies
from app.graph.state import ConversationState, ensure_state_defaults
from app.observability import log_event


def make_interpret_node(logger):
    def interpret(state: ConversationState) -> ConversationState:
        state = ensure_state_defaults(state)
        message = (state.get("incoming_message") or "").strip()
        requested_action = policies.extract_requested_action(message, state)
        state["requested_action"] = requested_action
        if requested_action in policies.PROTECTED_ACTIONS and not state.get("verified"):
            state["deferred_action"] = requested_action

        phone = policies.extract_phone(message)
        dob = policies.extract_dob(message)
        name = policies.extract_full_name(message)
        if state.get("provided_phone") is None and phone:
            state["provided_phone"] = phone
        if state.get("provided_dob") is None and dob:
            state["provided_dob"] = dob
        if state.get("provided_full_name") is None and name:
            state["provided_full_name"] = name

        if requested_action in {"confirm_appointment", "cancel_appointment"}:
            state["appointment_reference"] = policies.extract_appointment_reference(message)
        else:
            state["appointment_reference"] = None

        state["missing_verification_fields"] = policies.missing_verification_fields(state)
        log_event(logger, "parse_intent_and_entities", state, appointment_reference=state.get("appointment_reference"))
        return state

    return interpret
