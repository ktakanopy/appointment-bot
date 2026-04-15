from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.application.contracts.conversation import ConversationWorkflowInput, ConversationWorkflowResult


@runtime_checkable
class ConversationWorkflow(Protocol):
    def run(self, workflow_input: ConversationWorkflowInput) -> ConversationWorkflowResult:
        ...
