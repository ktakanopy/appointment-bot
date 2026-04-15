from __future__ import annotations

from app.application.contracts.conversation import ConversationWorkflowResult
from app.application.services.response_policy import ResponsePolicy
from app.llm.base import LLMProvider


class ChatResponseService:
    def __init__(self, provider: LLMProvider, response_policy: ResponsePolicy):
        self.provider = provider
        self.response_policy = response_policy

    def generate(self, workflow_result: ConversationWorkflowResult) -> str:
        fallback_text = self.response_policy.build_fallback_text(workflow_result)
        response = self.provider.generate_response(
            self._provider_state(workflow_result),
            fallback_text,
        )
        return response.response_text

    def _provider_state(self, workflow_result: ConversationWorkflowResult) -> dict[str, object]:
        return {
            "verification": workflow_result.verification.model_dump(mode="json"),
            "turn": workflow_result.turn.model_dump(mode="json"),
            "listed_appointments": [appointment.model_dump(mode="json") for appointment in workflow_result.listed_appointments],
        }
