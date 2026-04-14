from __future__ import annotations

import pytest
import app.graph.builder as builder_module
import app.runtime as runtime_module

from app.domain import policies
from app.llm.schemas import AssistantResponse, IntentPrediction, JudgeResult


class TestProvider:
    name = "test"

    def interpret(self, message, state):
        return IntentPrediction(
            requested_action=policies.extract_requested_action(message, state),
            full_name=policies.extract_full_name(message),
            phone=policies.extract_phone(message),
            dob=policies.extract_dob(message),
            appointment_reference=policies.extract_appointment_reference(message),
        )

    def generate_response(self, state, fallback_text):
        return AssistantResponse(response_text=fallback_text)

    def judge(self, scenario, transcript, observed_outcomes):
        return JudgeResult(status="pass", summary="Test judge completed.", score=1.0)


@pytest.fixture(autouse=True)
def isolate_runtime_settings(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.setenv("TRACING_ENABLED", "false")
    monkeypatch.setattr(builder_module, "build_provider", lambda settings, logger, tracer=None: TestProvider())
    monkeypatch.setattr(runtime_module, "build_provider", lambda settings, logger, tracer=None: TestProvider())
