from concurrent.futures import ThreadPoolExecutor

from app.models import ConversationOperation, ConversationWorkflowInput
from tests.support import build_test_workflow


def test_graph_keeps_parallel_sessions_isolated():
    workflow = build_test_workflow()

    def run_flow(index: int):
        thread_id = f"graph-parallel-{index}"
        result = None
        for message in ["show my appointments", "Ana Silva", "11999998888", "1990-05-10"]:
            result = workflow.run(ConversationWorkflowInput(thread_id=thread_id, incoming_message=message))
        return result

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(run_flow, range(5)))

    assert all(result.verification.verified is True for result in results)
    assert all(result.turn.requested_operation == ConversationOperation.LIST_APPOINTMENTS for result in results)
    assert all(len(result.listed_appointments) == 2 for result in results)
