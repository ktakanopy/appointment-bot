from __future__ import annotations

from app.domain import policies
from app.graph.state import ConversationState
from app.observability import log_event


def make_interpret_node(logger, provider=None):
    def interpret(state: ConversationState) -> ConversationState:
        message = (state.get("incoming_message") or "").strip()
        deterministic_action = policies.extract_requested_action(message, state)
        requested_action = deterministic_action
        provider_result = None
        if provider is not None:
            try:
                provider_result = provider.interpret(message, state)
            except Exception:
                state["provider_error"] = "interpret_failed"
                state["error_code"] = state.get("error_code") or "provider_fallback"
        if provider_result is not None:
            if deterministic_action == "unknown" and provider_result.requested_action != "unknown":
                requested_action = provider_result.requested_action
            if state.get("provided_phone") is None and provider_result.phone:
                state["provided_phone"] = provider_result.phone
            if state.get("provided_dob") is None and provider_result.dob:
                state["provided_dob"] = provider_result.dob
            if state.get("provided_full_name") is None and provider_result.full_name:
                state["provided_full_name"] = provider_result.full_name
            if provider_result.appointment_reference:
                state["appointment_reference"] = provider_result.appointment_reference
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

        if requested_action in {"confirm_appointment", "cancel_appointment"} and not state.get("appointment_reference"):
            state["appointment_reference"] = policies.extract_appointment_reference(message)
        else:
            if requested_action not in {"confirm_appointment", "cancel_appointment"}:
                state["appointment_reference"] = None

        state["missing_verification_fields"] = policies.missing_verification_fields(state)
        log_event(
            logger,
            "parse_intent_and_entities",
            state,
            appointment_reference=state.get("appointment_reference"),
            provider_error=state.get("provider_error"),
        )
        return state

    return interpret
