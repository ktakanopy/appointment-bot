from __future__ import annotations

from app.graph.state import ConversationState, ensure_state_defaults
from app.observability import log_event


def make_help_node(logger):
    def help_or_unknown(state: ConversationState) -> ConversationState:
        state = ensure_state_defaults(state)
        state["requested_action"] = "help"
        state["response_text"] = (
            "I can help you verify your identity, list your appointments, confirm one, or cancel one. "
            "Tell me what you would like to do."
        )
        log_event(logger, "handle_help_or_unknown", state)
        return state

    return help_or_unknown


def make_response_node(logger):
    def generate_response(state: ConversationState) -> ConversationState:
        state = ensure_state_defaults(state)
        if not state.get("response_text"):
            state["response_text"] = "I couldn't complete that request right now. Please try again."
        state["messages"].append({"role": "assistant", "content": state["response_text"]})
        log_event(logger, "generate_response", state)
        return state

    return generate_response
