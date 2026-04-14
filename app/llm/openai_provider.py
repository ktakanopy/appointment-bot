from __future__ import annotations

import json
from typing import Any, TypeVar

from openai import OpenAI
from pydantic import BaseModel

from app.config import ProviderSettings
from app.llm.schemas import AssistantResponse, IntentPrediction, JudgeResult
from app.observability import record_provider_event
from app.prompts.intent_prompt import INTENT_PROMPT
from app.prompts.response_prompt import RESPONSE_PROMPT

T = TypeVar("T", bound=BaseModel)


class OpenAIProvider:
    name = "openai"

    def __init__(self, settings: ProviderSettings, logger, tracer=None, client: Any | None = None):
        self.settings = settings
        self.logger = logger
        self.tracer = tracer
        self.client = client or OpenAI(api_key=settings.api_key, timeout=settings.timeout_seconds)

    def interpret(self, message: str, state: dict[str, Any]) -> IntentPrediction:
        verification = state.get("verification", {})
        turn = state.get("turn", {})
        payload = {
            "message": message,
            "state": {
                "verified": verification.get("verified", False),
                "requested_action": turn.get("requested_action"),
                "deferred_action": turn.get("deferred_action"),
                "missing_verification_fields": state.get("missing_verification_fields", []),
            },
        }
        return self._complete_model(
            event_name="interpret",
            response_model=IntentPrediction,
            system_message=INTENT_PROMPT,
            payload=payload,
        )

    def generate_response(self, state: dict[str, Any], fallback_text: str) -> AssistantResponse:
        verification = state.get("verification", {})
        turn = state.get("turn", {})
        payload = {
            "fallback_text": fallback_text,
            "requested_action": turn.get("requested_action"),
            "verified": verification.get("verified"),
            "error_code": turn.get("error_code"),
            "last_action_result": turn.get("last_action_result"),
        }
        return self._complete_model(
            event_name="generate_response",
            response_model=AssistantResponse,
            system_message=RESPONSE_PROMPT
            + "\nKeep the same meaning as fallback_text and do not invent new policy decisions.",
            payload=payload,
        )

    def judge(self, scenario: dict[str, Any], transcript: list[dict[str, Any]], observed_outcomes: dict[str, Any]) -> JudgeResult:
        payload = {
            "scenario": scenario,
            "transcript": transcript,
            "observed_outcomes": observed_outcomes,
        }
        return self._complete_model(
            event_name="judge",
            response_model=JudgeResult,
            system_message=(
                "Return strict JSON with keys status, summary, and score. "
                "Use status values pass, fail, or error. Score should be between 0 and 1 when present."
            ),
            payload=payload,
        )

    def _complete_model(
        self,
        *,
        event_name: str,
        response_model: type[T],
        system_message: str,
        payload: dict[str, Any],
    ) -> T:
        try:
            content = self._complete(
                system_message=system_message,
                user_message=json.dumps(payload, ensure_ascii=True),
            )
            result = response_model.model_validate_json(content)
        except Exception as exc:
            record_provider_event(
                self.logger,
                self.tracer,
                event_name,
                {"provider": self.name, "status": "error", "error_type": type(exc).__name__},
            )
            raise
        record_provider_event(self.logger, self.tracer, event_name, {"provider": self.name, "status": "ok"})
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
            content = "".join(self._extract_text_part(part) for part in message)
        else:
            content = message or ""
        if not content.strip():
            raise ValueError("OpenAI returned empty content")
        return content

    def _extract_text_part(self, part: Any) -> str:
        if isinstance(part, dict):
            text = part.get("text")
            return text if isinstance(text, str) else ""
        text = getattr(part, "text", "")
        return text if isinstance(text, str) else ""
