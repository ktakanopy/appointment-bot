from __future__ import annotations

from app.application.contracts.conversation import ConversationWorkflowResult
from app.application.services.response_policy import ResponsePolicy


class ChatResponseService:
    def __init__(self, response_policy: ResponsePolicy):
        self.response_policy = response_policy

    def generate(self, workflow_result: ConversationWorkflowResult) -> str:
        return self.response_policy.build_fallback_text(workflow_result)
