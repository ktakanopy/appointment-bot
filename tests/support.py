from __future__ import annotations

import logging
import re

from langgraph.checkpoint.memory import InMemorySaver

from app.graph.builder import build_graph
from app.graph.parsing import (
    extract_dob,
    extract_full_name,
    extract_phone,
    extract_requested_operation,
)
from app.graph.workflow import LangGraphWorkflow
from app.llm.schemas import IntentPrediction, JudgeResult
from app.repositories import InMemoryAppointmentRepository, InMemoryPatientRepository
from app.services import AppointmentService, VerificationService

_ORDINAL_WORDS = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3}


def _extract_selected_index(message: str) -> int | None:
    """Extract a 1-based appointment index from a message.

    Recognises ordinal words (first, second, third) and bare numbers (1, 2, 3).
    Returns None when no numeric reference is found.
    """
    lowered = message.lower()
    for word, index in _ORDINAL_WORDS.items():
        if word in lowered:
            return index
    match = re.search(r"\b(\d+)\b", lowered)
    if match:
        return int(match.group(1))
    return None


class TestProvider:
    name = "test"

    def interpret(self, message, state):
        return IntentPrediction(
            requested_operation=extract_requested_operation(message, state),
            full_name=extract_full_name(message),
            phone=extract_phone(message),
            dob=extract_dob(message),
            selected_index=_extract_selected_index(message),
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
        checkpointer=InMemorySaver(),
    )


def build_test_workflow(provider=None):
    graph = build_test_graph(provider=provider)
    return LangGraphWorkflow(
        graph,
        logger=logging.getLogger("appointment_bot"),
        tracer=None,
    )
