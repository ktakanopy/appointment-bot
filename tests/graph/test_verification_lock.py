from app.graph.builder import build_graph


def test_graph_locks_session_after_three_failed_verification_attempts():
    graph = build_graph()
    config = {"configurable": {"thread_id": "graph-lock"}}

    final = None
    for _ in range(3):
        graph.invoke({"thread_id": "graph-lock", "incoming_message": "show my appointments"}, config)
        graph.invoke({"thread_id": "graph-lock", "incoming_message": "Wrong Name"}, config)
        graph.invoke({"thread_id": "graph-lock", "incoming_message": "11000000000"}, config)
        final = graph.invoke({"thread_id": "graph-lock", "incoming_message": "1999-01-01"}, config)

    assert final is not None
    assert final["verification_status"] == "locked"
    assert final["verification_locked"] is True
    assert final["error_code"] == "verification_locked"
