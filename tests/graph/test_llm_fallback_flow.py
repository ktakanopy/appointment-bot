from __future__ import annotations

import pytest

from app.models import DependencyUnavailableError
from tests.support import build_test_workflow


class BrokenProvider:
    name = "broken"

    def interpret(self, message, state):
        raise RuntimeError("interpret failed")

    def judge(self, scenario, transcript, observed_outcomes):
        raise RuntimeError("judge failed")


def test_graph_raises_controlled_error_when_provider_fails():
    workflow = build_test_workflow(provider=BrokenProvider())

    with pytest.raises(DependencyUnavailableError):
        workflow.run("graph-llm-fallback", "show my appointments")
