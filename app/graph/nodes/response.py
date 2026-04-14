from __future__ import annotations

from app.graph.state import ConversationState
from app.observability import log_event


def make_help_node(logger):
    def help_or_unknown(state: ConversationState) -> ConversationState:
        state["requested_action"] = "help"
        state["response_text"] = (
            "I can help you verify your identity, list your appointments, confirm one, or cancel one. "
            "Tell me what you would like to do."
        )
        log_event(logger, "handle_help_or_unknown", state)
        return state

    return help_or_unknown


def make_response_node(logger, provider=None):
    def generate_response(state: ConversationState) -> ConversationState:
        if not state.get("response_text"):
            state["response_text"] = "I couldn't complete that request right now. Please try again."
        if provider is not None:
            try:
                generated = provider.generate_response(state, state["response_text"])
                state["response_text"] = generated.response_text
            except Exception:
                state["provider_error"] = "response_failed"
                state["error_code"] = state.get("error_code") or "provider_fallback"
        state["messages"].append({"role": "assistant", "content": state["response_text"]})
        log_event(logger, "generate_response", state, provider_error=state.get("provider_error"))
        return state

    return generate_response
