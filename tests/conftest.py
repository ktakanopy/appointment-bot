from __future__ import annotations

import pytest
import app.graph.builder as builder_module
import app.runtime as runtime_module

from app.graph import text_extraction
from app.llm.schemas import AssistantResponse, IntentPrediction, JudgeResult


class TestProvider:
    name = "test"

    def interpret(self, message, state):
        return IntentPrediction(
            requested_action=text_extraction.extract_requested_action(message, state),
            full_name=text_extraction.extract_full_name(message),
            phone=text_extraction.extract_phone(message),
            dob=text_extraction.extract_dob(message),
            appointment_reference=text_extraction.extract_appointment_reference(message),
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
