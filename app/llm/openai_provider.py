from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from app.config import ProviderSettings
from app.llm.schemas import AssistantResponse, IntentPrediction, JudgeResult
from app.observability import record_provider_event
from app.prompts.intent_prompt import INTENT_PROMPT
from app.prompts.response_prompt import RESPONSE_PROMPT


class OpenAIProvider:
    name = "openai"

    def __init__(self, settings: ProviderSettings, logger, tracer=None):
        self.settings = settings
        self.logger = logger
        self.tracer = tracer
        self.client = OpenAI(api_key=settings.api_key, timeout=settings.timeout_seconds)

    def interpret(self, message: str, state: dict[str, Any]) -> IntentPrediction:
        payload = {
            "message": message,
            "state": {
                "verified": state.get("verified", False),
                "requested_action": state.get("requested_action"),
                "deferred_action": state.get("deferred_action"),
                "missing_verification_fields": state.get("missing_verification_fields", []),
            },
        }
        content = self._complete(
            system_message=INTENT_PROMPT,
            user_message=json.dumps(payload, ensure_ascii=True),
        )
        result = IntentPrediction.model_validate_json(content)
        record_provider_event(self.logger, self.tracer, "interpret", {"provider": self.name, "status": "ok"})
        return result

    def generate_response(self, state: dict[str, Any], fallback_text: str) -> AssistantResponse:
        payload = {
            "fallback_text": fallback_text,
            "requested_action": state.get("requested_action"),
            "verified": state.get("verified"),
            "error_code": state.get("error_code"),
            "last_action_result": state.get("last_action_result"),
        }
        content = self._complete(
            system_message=RESPONSE_PROMPT
            + "\nKeep the same meaning as fallback_text and do not invent new policy decisions.",
            user_message=json.dumps(payload, ensure_ascii=True),
        )
        result = AssistantResponse.model_validate_json(content)
        record_provider_event(self.logger, self.tracer, "generate_response", {"provider": self.name, "status": "ok"})
        return result

    def judge(self, scenario: dict[str, Any], transcript: list[dict[str, Any]], observed_outcomes: dict[str, Any]) -> JudgeResult:
        payload = {
            "scenario": scenario,
            "transcript": transcript,
            "observed_outcomes": observed_outcomes,
        }
        content = self._complete(
            system_message=(
                "Return strict JSON with keys status, summary, and score. "
                "Use status values pass, fail, or error. Score should be between 0 and 1 when present."
            ),
            user_message=json.dumps(payload, ensure_ascii=True),
        )
        result = JudgeResult.model_validate_json(content)
        record_provider_event(self.logger, self.tracer, "judge", {"provider": self.name, "status": "ok"})
        return result

    def _complete(self, system_message: str, user_message: str) -> str:
        response = self.client.chat.completions.create(
            model=self.settings.model_name,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ],
        )
        message = response.choices[0].message.content
        if isinstance(message, list):
            return "".join(part.get("text", "") for part in message if isinstance(part, dict))
        return message or "{}"
