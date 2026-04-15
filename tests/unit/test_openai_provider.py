from __future__ import annotations

import logging
import time

import pytest

from app.config import ProviderSettings
from app.llm.provider import OpenAIProvider
from app.models import ConversationOperation


class FakeParsedCompletions:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def parse(self, **kwargs):
        outcome = self.outcomes[min(self.calls, len(self.outcomes) - 1)]
        self.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        message = type("Message", (), outcome)
        choice = type("Choice", (), {"message": message})
        return type("Response", (), {"choices": [choice]})


class FakeBetaChat:
    def __init__(self, outcomes):
        self.completions = FakeParsedCompletions(outcomes)


class FakeClient:
    def __init__(self, outcomes):
        self.beta = type("FakeBeta", (), {"chat": FakeBetaChat(outcomes)})()


def _provider(outcomes=None) -> OpenAIProvider:
    outcomes = outcomes or [{"parsed": IntentPayload.list_appointments()}]
    return OpenAIProvider(
        ProviderSettings(
            provider_name="openai",
            model_name="gpt-4o-mini",
            api_key="test-key",
            timeout_seconds=20,
        ),
        logger=logging.getLogger("appointment_bot"),
        client=FakeClient(outcomes),
    )


class IntentPayload:
    @staticmethod
    def list_appointments():
        return {
            "requested_operation": "list_appointments",
            "full_name": "Ana Silva",
            "phone": "11999998888",
            "dob": "1990-05-10",
            "appointment_reference": None,
        }


def test_openai_provider_parses_structured_intent_response():
    provider = _provider([{"parsed": IntentPayload.list_appointments()}])

    result = provider.interpret("show my appointments", {"verified": False})

    assert result.requested_operation == ConversationOperation.LIST_APPOINTMENTS
    assert result.full_name == "Ana Silva"


def test_openai_provider_raises_for_missing_parsed_content():
    provider = _provider([{"parsed": None, "refusal": None}])

    with pytest.raises(ValueError, match="no parsed content"):
        provider.interpret("show my appointments", {"verified": False})


def test_openai_provider_retries_transient_failures(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda *_args, **_kwargs: None)
    provider = _provider([RuntimeError("boom"), {"parsed": IntentPayload.list_appointments()}])

    result = provider.interpret("show my appointments", {"verified": False})

    assert result.requested_operation == ConversationOperation.LIST_APPOINTMENTS
    assert provider.client.beta.chat.completions.calls == 2
