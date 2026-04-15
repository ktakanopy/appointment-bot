from __future__ import annotations

import logging

from app.domain.services import AppointmentService, VerificationService
from app.graph.builder import build_graph
from app.graph import text_extraction
from app.infrastructure.persistence.in_memory import InMemoryAppointmentRepository, InMemoryPatientRepository
from app.infrastructure.workflow.in_memory_checkpoint import InMemoryCheckpointStore
from app.infrastructure.workflow.langgraph_runner import LangGraphConversationWorkflow
from app.llm.schemas import IntentPrediction, JudgeResult


class TestProvider:
    name = "test"

    def interpret(self, message, state):
        return IntentPrediction(
            requested_operation=text_extraction.extract_requested_operation(message, state),
            full_name=text_extraction.extract_full_name(message),
            phone=text_extraction.extract_phone(message),
            dob=text_extraction.extract_dob(message),
            appointment_reference=text_extraction.extract_appointment_reference(message),
        )

    def judge(self, scenario, transcript, observed_outcomes):
        return JudgeResult(status="pass", summary="Test judge completed.", score=1.0)


def build_test_graph(provider=None):
    return build_graph(
        logger=logging.getLogger("appointment_bot"),
        provider=provider or TestProvider(),
        verification_service=VerificationService(InMemoryPatientRepository()),
        appointment_service=AppointmentService(InMemoryAppointmentRepository()),
        max_verification_attempts=3,
        checkpointer=InMemoryCheckpointStore().build_checkpointer(),
    )


def build_test_workflow(provider=None):
    graph = build_test_graph(provider=provider)
    return LangGraphConversationWorkflow(
        graph,
        logger=logging.getLogger("appointment_bot"),
        tracer=None,
    )
