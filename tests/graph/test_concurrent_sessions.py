from concurrent.futures import ThreadPoolExecutor

from app.graph.builder import build_graph


def test_graph_keeps_parallel_sessions_isolated():
    graph = build_graph()

    def run_flow(index: int):
        thread_id = f"graph-parallel-{index}"
        config = {"configurable": {"thread_id": thread_id}}
        result = None
        for message in ["show my appointments", "Ana Silva", "11999998888", "1990-05-10"]:
            result = graph.invoke({"thread_id": thread_id, "incoming_message": message}, config)
        return result

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(run_flow, range(5)))

    assert all(result["verified"] is True for result in results)
    assert all(result["requested_action"] == "list_appointments" for result in results)
    assert all(len(result["listed_appointments"]) == 2 for result in results)
