from __future__ import annotations

from app.graph.state import ConversationState
from app.models import ConversationWorkflowInput
from app.observability import record_trace_event


class LangGraphWorkflow:
    def __init__(self, graph, logger, tracer=None):
        self.graph = graph
        self.logger = logger
        self.tracer = tracer

    def run(
        self,
        workflow_input: ConversationWorkflowInput | str,
        incoming_message: str | None = None,
    ) -> ConversationState:
        if hasattr(workflow_input, "thread_id") and hasattr(workflow_input, "incoming_message"):
            thread_id = workflow_input.thread_id
            message = workflow_input.incoming_message
        else:
            thread_id = workflow_input
            message = incoming_message or ""
        payload = {"thread_id": thread_id, "incoming_message": message}
        config = {"configurable": {"thread_id": thread_id}}
        record_trace_event(
            self.logger,
            self.tracer,
            "workflow.start",
            {"thread_id": thread_id, "payload": payload},
        )
        result = self.graph.invoke(payload, config)
        record_trace_event(
            self.logger,
            self.tracer,
            "workflow.end",
            {"thread_id": thread_id, "result": result},
        )
        return ConversationState.model_validate(result)
