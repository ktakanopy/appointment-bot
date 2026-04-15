from __future__ import annotations

from typing import Protocol

from app.application.contracts.conversation import ConversationWorkflowInput, ConversationWorkflowResult


class ConversationWorkflow(Protocol):
    def run(self, workflow_input: ConversationWorkflowInput) -> ConversationWorkflowResult:
        ...
