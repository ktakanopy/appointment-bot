from __future__ import annotations

import app.graph.builder as builder_module


class BrokenProvider:
    name = "broken"

    def interpret(self, message, state):
        raise RuntimeError("interpret failed")

    def generate_response(self, state, fallback_text):
        raise RuntimeError("response failed")

    def judge(self, scenario, transcript, observed_outcomes):
        raise RuntimeError("judge failed")


def test_graph_uses_deterministic_fallback_when_provider_fails(monkeypatch):
    monkeypatch.setattr(builder_module, "build_provider", lambda settings, logger: BrokenProvider())
    graph = builder_module.build_graph()
    config = {"configurable": {"thread_id": "graph-llm-fallback"}}

    for message in ["show my appointments", "Ana Silva", "11999998888"]:
        graph.invoke({"thread_id": "graph-llm-fallback", "incoming_message": message}, config)

    final = graph.invoke({"thread_id": "graph-llm-fallback", "incoming_message": "1990-05-10"}, config)

    assert final["verified"] is True
    assert final["requested_action"] == "list_appointments"
    assert final["error_code"] == "provider_fallback"
