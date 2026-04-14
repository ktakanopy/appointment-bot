from __future__ import annotations

from app.graph.state import ConversationState
from app.observability import log_event


def make_help_node(logger):
    def help_or_unknown(state: ConversationState) -> ConversationState:
        state["requested_action"] = "help"
        if state.get("verified"):
            state["response_text"] = (
                "You are verified. You can ask me to list your appointments, confirm one, or cancel one."
            )
        else:
            state["response_text"] = "I need to verify your identity first. Please tell me your full name."
        log_event(logger, "handle_help_or_unknown", state)
        return state

    return help_or_unknown


def make_response_node(logger, provider):
    def generate_response(state: ConversationState) -> ConversationState:
        if not state.get("response_text"):
            state["response_text"] = "I couldn't complete that request right now. Please try again."
        generated = provider.generate_response(state, state["response_text"])
        state["response_text"] = generated.response_text
        state["messages"].append({"role": "assistant", "content": state["response_text"]})
        log_event(logger, "generate_response", state)
        return state

    return generate_response
