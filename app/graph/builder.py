from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.domain.services import AppointmentService, VerificationService
from app.graph.nodes.appointments import (
    make_cancel_node,
    make_confirm_node,
    make_execute_action_node,
    make_list_node,
)
from app.graph.nodes.ingest import make_ingest_node
from app.graph.nodes.interpret import make_interpret_node
from app.graph.nodes.response import make_help_node
from app.graph.routing import route_after_interpret, route_after_verify
from app.graph.nodes.verification import make_verification_node
from app.graph.state import ConversationState
from app.llm.base import LLMProvider


def build_graph(
    *,
    logger: logging.Logger,
    provider: LLMProvider,
    verification_service: VerificationService,
    appointment_service: AppointmentService,
    max_verification_attempts: int,
    checkpointer: Any,
):
    list_node = make_list_node(appointment_service, logger)
    confirm_node = make_confirm_node(appointment_service, logger)
    cancel_node = make_cancel_node(appointment_service, logger)
    help_node = make_help_node(logger)

    builder = StateGraph(ConversationState)
    builder.add_node("ingest_user_message", make_ingest_node(logger))
    builder.add_node("parse_intent_and_entities", make_interpret_node(logger, provider=provider))
    builder.add_node(
        "verify",
        make_verification_node(
            verification_service,
            logger,
            max_verification_attempts,
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

    builder.add_edge(START, "ingest_user_message")
    builder.add_edge("ingest_user_message", "parse_intent_and_entities")
    builder.add_conditional_edges(
        "parse_intent_and_entities",
        route_after_interpret,
        {
            "verify": "verify",
            "execute_action": "execute_action",
        },
    )
    builder.add_conditional_edges(
        "verify",
        route_after_verify,
        {
            "end": END,
            "execute_action": "execute_action",
        },
    )
    builder.add_edge("execute_action", END)

    return builder.compile(checkpointer=checkpointer)
