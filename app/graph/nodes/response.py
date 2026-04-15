from __future__ import annotations

from app.graph.state import ConversationState, turn_state, verification_state
from app.observability import log_event


def make_help_node(logger):
    def help_or_unknown(state: ConversationState) -> ConversationState:
        verification = verification_state(state)
        turn = turn_state(state)
        turn.requested_action = "help"
        if verification.verified:
            turn.response_text = (
                "I'm CAPY. You are verified. You can ask me to list your appointments, confirm one, or cancel one."
            )
        else:
            turn.response_text = "I'm CAPY. I need to verify your identity first. Please tell me your full name."
        log_event(logger, "handle_help_or_unknown", state)
        return state

    return help_or_unknown


def make_response_node(logger, provider):
    def generate_response(state: ConversationState) -> ConversationState:
        turn = turn_state(state)
        if not turn.response_text:
            turn.response_text = "I couldn't complete that request right now. Please try again."
        generated = provider.generate_response(state, turn.response_text)
        turn.response_text = generated.response_text
        state.add_assistant_message(turn.response_text)
        log_event(logger, "generate_response", state)
        return state

    return generate_response
