"""Intent/entity regression tests using the deterministic TestProvider.

These tests validate that the structured interpretation pipeline
(provider.interpret + field normalization) returns expected outputs
for a curated set of user utterances.  They protect against drift
after changes to text_extraction, normalization, or prompt logic.

NOTE: These tests use the deterministic TestProvider which relies on
rule-based text extraction.  To test against a live LLM provider,
replace the provider fixture and adjust expected values as needed.
"""

from __future__ import annotations

import pytest

from app.evals.intent_entity_loader import load_intent_entity_cases
from app.graph.parsing import normalize_dob, normalize_full_name, normalize_phone
from tests.support import TestProvider


def _interpret_and_normalize(provider, utterance: str, state: dict | None = None) -> dict:
    """Run provider.interpret then apply the same normalization as production."""
    state = state or {}
    result = provider.interpret(utterance, state)
    return {
        "requested_operation": result.requested_operation.value,
        "full_name": normalize_full_name(result.full_name),
        "phone": normalize_phone(result.phone),
        "dob": normalize_dob(result.dob),
        "appointment_reference": result.appointment_reference,
    }


CASES = load_intent_entity_cases()


@pytest.mark.parametrize(
    "case",
    CASES,
    ids=[c.get("id", c["utterance"][:40]) for c in CASES],
)
def test_intent_entity_regression(case):
    provider = TestProvider()
    observed = _interpret_and_normalize(provider, case["utterance"], case.get("state"))
    expected = case["expected"]
    for key, expected_value in expected.items():
        assert observed[key] == expected_value, (
            f"Field '{key}' mismatch for utterance: {case['utterance']!r}\n"
            f"  expected: {expected_value!r}\n"
            f"  observed: {observed[key]!r}"
        )
