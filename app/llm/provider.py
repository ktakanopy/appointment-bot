from __future__ import annotations

import json
import time
from typing import Any, TypeVar

from openai import OpenAI
from pydantic import BaseModel

from app.config import ProviderSettings
from app.llm.prompt import INTENT_PROMPT
from app.llm.schemas import IntentPrediction, JudgeResult
from app.observability import record_provider_event, trace_generation

T = TypeVar("T", bound=BaseModel)

MAX_PARSE_ATTEMPTS = 3
BASE_RETRY_SECONDS = 0.1


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
                "requested_operation": turn.get("requested_operation"),
                "missing_verification_fields": state.get("missing_verification_fields", []),
                "messages": state.get("messages", []),
            },
        }
        return self._complete_model(
            event_name="interpret",
            response_model=IntentPrediction,
            system_message=INTENT_PROMPT,
            payload=payload,
            thread_id=state.get("thread_id"),
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
            thread_id=scenario.get("scenario_id"),
        )

    def _complete_model(
        self,
        *,
        event_name: str,
        response_model: type[T],
        system_message: str,
        payload: dict[str, Any],
        thread_id: str | None,
    ) -> T:
        generation_input = {
            "system_message": system_message,
            "payload": payload,
            "response_model": response_model.__name__,
        }
        try:
            with trace_generation(
                self.logger,
                self.tracer,
                thread_id=thread_id,
                name=f"provider.{event_name}",
                model=self.settings.model_name,
                input_payload=generation_input,
                metadata={
                    "provider": self.name,
                    "response_model": response_model.__name__,
                    "timeout_seconds": self.settings.timeout_seconds,
                },
            ) as generation:
                result = self._complete_with_retries(
                    response_model=response_model,
                    system_message=system_message,
                    user_message=json.dumps(payload, ensure_ascii=True, default=str),
                    event_name=event_name,
                    thread_id=thread_id,
                )
                if generation is not None:
                    generation.update(output=result.model_dump(mode="json"))
        except Exception as exc:
            record_provider_event(
                self.logger,
                self.tracer,
                event_name,
                {
                    "provider": self.name,
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "thread_id": thread_id,
                    "response_model": response_model.__name__,
                },
            )
            raise
        record_provider_event(
            self.logger,
            self.tracer,
            event_name,
            {
                "provider": self.name,
                "status": "ok",
                "thread_id": thread_id,
                "response_model": response_model.__name__,
            },
        )
        return result

    def _complete_with_retries(
        self,
        *,
        response_model: type[T],
        system_message: str,
        user_message: str,
        event_name: str,
        thread_id: str | None,
    ) -> T:
        last_error: Exception | None = None
        for attempt in range(MAX_PARSE_ATTEMPTS):
            try:
                return self._complete(
                    response_model=response_model,
                    system_message=system_message,
                    user_message=user_message,
                )
            except Exception as error:
                last_error = error
                record_provider_event(
                    self.logger,
                    self.tracer,
                    f"{event_name}.retry",
                    {
                        "provider": self.name,
                        "status": "retry",
                        "thread_id": thread_id,
                        "attempt": attempt + 1,
                        "max_attempts": MAX_PARSE_ATTEMPTS,
                        "error_type": type(error).__name__,
                    },
                )
                if attempt == MAX_PARSE_ATTEMPTS - 1:
                    raise
                time.sleep(BASE_RETRY_SECONDS * (2**attempt))

    def _complete(
        self,
        *,
        response_model: type[T],
        system_message: str,
        user_message: str,
    ) -> T:
        response = self.client.beta.chat.completions.parse(
            model=self.settings.model_name,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ],
            response_format=response_model,
        )
        message = response.choices[0].message
        parsed = getattr(message, "parsed", None)
        if parsed is not None:
            return response_model.model_validate(parsed)
        refusal = getattr(message, "refusal", None)
        if refusal:
            raise ValueError(f"OpenAI refused structured output: {refusal}")
        raise ValueError("OpenAI returned no parsed content")
