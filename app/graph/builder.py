from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.graph.nodes import (
    make_cancel_node,
    make_confirm_node,
    make_execute_action_node,
    make_help_node,
    make_ingest_node,
    make_interpret_node,
    make_list_node,
    make_verification_node,
)
from app.graph.routing import route_after_interpret, route_after_verify
from app.graph.state import ConversationState


def build_graph(
    *,
    logger: logging.Logger,
    provider,
    verification_service,
    appointment_service,
    max_verification_attempts: int,
    checkpointer: Any,
):
    list_node = make_list_node(appointment_service, logger)
    confirm_node = make_confirm_node(appointment_service, logger)
    cancel_node = make_cancel_node(appointment_service, logger)
    help_node = make_help_node(logger)

    builder = StateGraph(ConversationState)
    builder.add_node("ingest", make_ingest_node(logger))
    builder.add_node("interpret", make_interpret_node(logger, provider=provider))
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

    builder.add_edge(START, "ingest")
    builder.add_edge("ingest", "interpret")
    builder.add_conditional_edges(
        "interpret",
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
