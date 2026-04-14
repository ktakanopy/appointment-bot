from __future__ import annotations

import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from app.config import load_settings
from app.domain.services import AppointmentService, VerificationService
from app.graph.nodes.appointments import make_cancel_node, make_confirm_node, make_list_node
from app.graph.nodes.ingest import make_ingest_node
from app.graph.nodes.interpret import make_interpret_node
from app.graph.nodes.response import make_help_node, make_response_node
from app.graph.routing import route_after_interpret, route_after_verification
from app.graph.state import ConversationState
from app.graph.subgraphs.verification_subgraph import build_verification_subgraph
from app.observability import get_logger
from app.llm.factory import build_provider
from app.repositories.in_memory import InMemoryAppointmentRepository, InMemoryPatientRepository


def build_graph(
    *,
    logger=None,
    settings=None,
    verification_service=None,
    appointment_service=None,
):
    settings = settings or load_settings()
    logger = logger or get_logger()
    if verification_service is None:
        patient_repository = InMemoryPatientRepository()
        verification_service = VerificationService(patient_repository)
    if appointment_service is None:
        appointment_repository = InMemoryAppointmentRepository()
        appointment_service = AppointmentService(appointment_repository)
    provider = build_provider(settings, logger)

    builder = StateGraph(ConversationState)
    builder.add_node("ingest_user_message", make_ingest_node(logger))
    builder.add_node("parse_intent_and_entities", make_interpret_node(logger, provider=provider))
    builder.add_node("verification_subgraph", build_verification_subgraph(verification_service, logger))
    builder.add_node("list_appointments", make_list_node(appointment_service, logger))
    builder.add_node("confirm_appointment", make_confirm_node(appointment_service, logger))
    builder.add_node("cancel_appointment", make_cancel_node(appointment_service, logger))
    builder.add_node("handle_help_or_unknown", make_help_node(logger))
    builder.add_node("generate_response", make_response_node(logger, provider=provider))

    builder.add_edge(START, "ingest_user_message")
    builder.add_edge("ingest_user_message", "parse_intent_and_entities")
    builder.add_conditional_edges(
        "parse_intent_and_entities",
        route_after_interpret,
        {
            "verification_subgraph": "verification_subgraph",
            "list_appointments": "list_appointments",
            "confirm_appointment": "confirm_appointment",
            "cancel_appointment": "cancel_appointment",
            "handle_help_or_unknown": "handle_help_or_unknown",
        },
    )
    builder.add_conditional_edges(
        "verification_subgraph",
        route_after_verification,
        {
            "list_appointments": "list_appointments",
            "confirm_appointment": "confirm_appointment",
            "cancel_appointment": "cancel_appointment",
            "handle_help_or_unknown": "handle_help_or_unknown",
            "generate_response": "generate_response",
        },
    )
    builder.add_edge("list_appointments", "generate_response")
    builder.add_edge("confirm_appointment", "generate_response")
    builder.add_edge("cancel_appointment", "generate_response")
    builder.add_edge("handle_help_or_unknown", "generate_response")
    builder.add_edge("generate_response", END)

    connection = sqlite3.connect(str(settings.checkpoint_database_path), check_same_thread=False)
    graph = builder.compile(checkpointer=SqliteSaver(connection))
    setattr(graph, "_sqlite_connection", connection)
    setattr(graph, "_provider", provider)
    return graph
