from __future__ import annotations

import logging

from app.graph.builder import build_graph
from app.infrastructure.workflow.langgraph_runner import LangGraphConversationWorkflow
from app.runtime_assembly.bundles import RepositoryBundle, ServiceBundle, WorkflowBundle


def build_workflow(
    *,
    logger: logging.Logger,
    tracer: object | None,
    repositories: RepositoryBundle,
    services: ServiceBundle,
    max_verification_attempts: int,
) -> WorkflowBundle:
    graph = build_graph(
        logger=logger,
        provider=services.provider,
        verification_service=services.verification_service,
        appointment_service=services.appointment_service,
        max_verification_attempts=max_verification_attempts,
        checkpointer=repositories.checkpoint_store.build_checkpointer(),
    )
    workflow = LangGraphConversationWorkflow(graph, logger, tracer=tracer)
    return WorkflowBundle(graph=graph, workflow=workflow)
