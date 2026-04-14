from __future__ import annotations

import app.graph.builder as builder_module
import pytest


class BrokenProvider:
    name = "broken"

    def interpret(self, message, state):
        raise RuntimeError("interpret failed")

    def generate_response(self, state, fallback_text):
        raise RuntimeError("response failed")

    def judge(self, scenario, transcript, observed_outcomes):
        raise RuntimeError("judge failed")


def test_graph_raises_when_provider_fails(monkeypatch):
    monkeypatch.setattr(builder_module, "build_provider", lambda settings, logger, tracer=None: BrokenProvider())
    graph = builder_module.build_graph()
    config = {"configurable": {"thread_id": "graph-llm-fallback"}}

    with pytest.raises(RuntimeError, match="interpret failed"):
        graph.invoke({"thread_id": "graph-llm-fallback", "incoming_message": "show my appointments"}, config)
