from __future__ import annotations

from app.evals.models import EvaluationScenario


CORE_SCENARIOS = [
    EvaluationScenario(
        scenario_id="verification-list",
        title="Verification gates appointment list",
        input_turns=["show my appointments", "Ana Silva", "11999998888", "1990-05-10"],
        expected_outcomes={"verified": True, "current_action": "list_appointments"},
        judge_rubric="The patient should be verified before appointments are returned.",
        category="verification",
    ),
    EvaluationScenario(
        scenario_id="ambiguous-cancel",
        title="Ambiguous cancellation asks for clarification",
        input_turns=["show my appointments", "Ana Silva", "11999998888", "1990-05-10", "cancel my appointment"],
        expected_outcomes={"error_code": "ambiguous_appointment_reference"},
        judge_rubric="The assistant should ask the user to clarify which appointment to cancel.",
        category="ambiguity",
    ),
    EvaluationScenario(
        scenario_id="idempotent-confirm",
        title="Repeated confirm remains idempotent",
        input_turns=[
            "show my appointments",
            "Ana Silva",
            "11999998888",
            "1990-05-10",
            "confirm the first one",
            "confirm the first one",
        ],
        expected_outcomes={"last_outcome": "already_confirmed"},
        judge_rubric="The second confirm should not produce a duplicate state change.",
        category="idempotency",
    ),
    EvaluationScenario(
        scenario_id="retry-after-failed-verification",
        title="Retry after a failed verification can still recover",
        input_turns=[
            "show my appointments",
            "Wrong Name",
            "11000000000",
            "1999-01-01",
            "Ana Silva",
            "11999998888",
            "1990-05-10",
        ],
        expected_outcomes={"verified": True, "current_action": "list_appointments"},
        judge_rubric="A single failed verification should not block a later successful retry in the same session.",
        category="verification",
    ),
    EvaluationScenario(
        scenario_id="confirm-without-list-context",
        title="Confirm without prior list asks for context",
        input_turns=[
            "Ana Silva",
            "11999998888",
            "1990-05-10",
            "confirm the first one",
        ],
        expected_outcomes={"error_code": "missing_list_context"},
        judge_rubric="The assistant should ask the patient to list appointments before using an ordinal reference.",
        category="context",
    ),
]
