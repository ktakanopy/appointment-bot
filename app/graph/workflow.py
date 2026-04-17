from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage

from app.graph.state import ConversationGraphInput, ConversationState, build_conversation_state, serialize_messages
from app.observability import record_trace_event, summarize_state_for_trace, trace_span


class LangGraphWorkflow:
    def __init__(self, graph, logger, tracer=None):
        self.graph = graph
        self.logger = logger
        self.tracer = tracer

    def run(self, thread_id: str, incoming_message: str) -> ConversationState:
        payload: ConversationGraphInput = {
            "thread_id": thread_id,
            "messages": [HumanMessage(content=incoming_message)],
        }
        config = {"configurable": {"thread_id": thread_id}}
        record_trace_event(
            self.logger,
            self.tracer,
            "workflow.start",
            {
                "thread_id": thread_id,
                "payload": {
                    "thread_id": thread_id,
                    "messages": serialize_messages(payload["messages"]),
                },
            },
        )
        with trace_span(
            self.logger,
            self.tracer,
            thread_id=thread_id,
            name="workflow.run",
            input_payload={
                "thread_id": thread_id,
                "incoming_message": incoming_message,
                "payload": {
                    "thread_id": thread_id,
                    "messages": serialize_messages(payload["messages"]),
                },
            },
            metadata={"component": "workflow"},
        ) as span:
            result = self.graph.invoke(payload, config)
            conversation_state = build_conversation_state(result)
            if span is not None:
                span.update(output=summarize_state_for_trace(conversation_state))
        record_trace_event(
            self.logger,
            self.tracer,
            "workflow.end",
            {"thread_id": thread_id, "result": conversation_state.model_dump(mode="json")},
        )
        return conversation_state

    def append_assistant_message(self, thread_id: str, content: str) -> None:
        if not content:
            return
        config = {"configurable": {"thread_id": thread_id}}
        self.graph.update_state(
            config,
            {
                "thread_id": thread_id,
                "messages": [AIMessage(content=content)],
            },
            as_node="execute_action",
        )
