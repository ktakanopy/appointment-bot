from __future__ import annotations

import logging

import pytest

from app.application.contracts.conversation import ConversationOperation
from app.config import ProviderSettings
from app.infrastructure.llm.openai_provider import OpenAIProvider


class FakeCompletions:
    def __init__(self, content: str):
        self.content = content

    def create(self, **kwargs):
        message = type("Message", (), {"content": self.content})
        choice = type("Choice", (), {"message": message})
        return type("Response", (), {"choices": [choice]})


class FakeChat:
    def __init__(self, content: str):
        self.completions = FakeCompletions(content)


class FakeClient:
    def __init__(self, content: str):
        self.chat = FakeChat(content)


def _provider(content: str = '{"response_text":"ok"}') -> OpenAIProvider:
    return OpenAIProvider(
        ProviderSettings(
            provider_name="openai",
            model_name="gpt-4o-mini",
            api_key="test-key",
            timeout_seconds=20,
        ),
        logger=logging.getLogger("appointment_bot"),
        client=FakeClient(content),
    )


def test_openai_provider_parses_structured_intent_response():
    provider = _provider(
        '{"requested_operation":"list_appointments","full_name":"Ana Silva","phone":"11999998888","dob":"1990-05-10","appointment_reference":null}'
    )

    result = provider.interpret("show my appointments", {"verified": False})

    assert result.requested_operation == ConversationOperation.LIST_APPOINTMENTS
    assert result.full_name == "Ana Silva"


def test_openai_provider_parses_structured_response_generation():
    provider = _provider('{"response_text":"Your appointment is confirmed."}')

    result = provider.generate_response({"requested_operation": "confirm_appointment"}, "fallback")

    assert result.response_text == "Your appointment is confirmed."


def test_openai_provider_raises_for_empty_content():
    provider = _provider("")

    with pytest.raises(ValueError, match="empty content"):
        provider.generate_response({"requested_operation": "confirm_appointment"}, "fallback")
