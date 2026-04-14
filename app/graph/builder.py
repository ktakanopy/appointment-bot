from __future__ import annotations

import logging

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.config import Settings, load_settings
from app.domain.services import AppointmentService, VerificationService
from app.graph.nodes.appointments import (
    make_cancel_node,
    make_confirm_node,
    make_execute_action_node,
    make_list_node,
)
from app.graph.nodes.ingest import make_ingest_node
from app.graph.nodes.interpret import make_interpret_node
from app.graph.nodes.response import make_help_node, make_response_node
from app.graph.nodes.verification import make_verification_node
from app.graph.state import ConversationState
from app.llm.base import LLMProvider
from app.llm.factory import build_provider
from app.observability import build_tracer, get_logger
from app.repositories.in_memory import InMemoryAppointmentRepository, InMemoryPatientRepository

_UNSET = object()


def build_graph(
    *,
    logger: logging.Logger | None = None,
    settings: Settings | None = None,
    tracer: object = _UNSET,
    provider: LLMProvider | object = _UNSET,
    verification_service: VerificationService | None = None,
    appointment_service: AppointmentService | None = None,
):
    """Build the linear conversation workflow with persisted per-session state."""
    settings = settings or load_settings()
    logger = logger or get_logger()
    if tracer is _UNSET:
        tracer = build_tracer(settings)
    if verification_service is None:
        patient_repository = InMemoryPatientRepository()
        verification_service = VerificationService(patient_repository)
    if appointment_service is None:
        appointment_repository = InMemoryAppointmentRepository()
        appointment_service = AppointmentService(appointment_repository)
    if provider is _UNSET:
        provider = build_provider(settings, logger, tracer=tracer)

    list_node = make_list_node(appointment_service, logger)
    confirm_node = make_confirm_node(appointment_service, logger)
    cancel_node = make_cancel_node(appointment_service, logger)
    help_node = make_help_node(logger)

    builder = StateGraph(ConversationState)
    builder.add_node("ingest_user_message", make_ingest_node(logger))
    builder.add_node("parse_intent_and_entities", make_interpret_node(logger, provider=provider))
    builder.add_node(
        "verify_or_prompt",
        make_verification_node(
            verification_service,
            logger,
            settings.max_verification_attempts,
        ),
    )
    builder.add_node(
        "execute_action",
        make_execute_action_node(
            logger,
            list_node=list_node,
            confirm_node=confirm_node,
            cancel_node=cancel_node,
            help_node=help_node,
        ),
    )
    builder.add_node("generate_response", make_response_node(logger, provider=provider))

    builder.add_edge(START, "ingest_user_message")
    builder.add_edge("ingest_user_message", "parse_intent_and_entities")
    builder.add_edge("parse_intent_and_entities", "verify_or_prompt")
    builder.add_edge("verify_or_prompt", "execute_action")
    builder.add_edge("execute_action", "generate_response")
    builder.add_edge("generate_response", END)

    return builder.compile(checkpointer=InMemorySaver())
