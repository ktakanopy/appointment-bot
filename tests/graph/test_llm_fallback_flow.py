from __future__ import annotations

from tests.support import build_test_workflow


class BrokenProvider:
    name = "broken"

    def interpret(self, message, state):
        raise RuntimeError("interpret failed")

    def judge(self, scenario, transcript, observed_outcomes):
        raise RuntimeError("judge failed")


def test_graph_uses_deterministic_fallback_when_provider_fails():
    workflow = build_test_workflow(provider=BrokenProvider())
    state = workflow.run("graph-llm-fallback", "show my appointments")

    assert state.turn.requested_operation.value == "verify_identity"
    assert state.turn.deferred_operation.value == "list_appointments"
    assert state.turn.response_key.value == "collect_full_name"
    assert state.verification.verified is False
