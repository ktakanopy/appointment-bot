from __future__ import annotations

from app.graph.builder import build_graph


def test_sqlite_checkpointer_persists_thread_state_across_graph_instances():
    first_graph = build_graph()
    config = {"configurable": {"thread_id": "persisted-thread"}}

    first_graph.invoke({"thread_id": "persisted-thread", "incoming_message": "show my appointments"}, config)
    first_graph.invoke({"thread_id": "persisted-thread", "incoming_message": "Ana Silva"}, config)

    second_graph = build_graph()
    second_result = second_graph.invoke({"thread_id": "persisted-thread", "incoming_message": "11999998888"}, config)
    final_result = second_graph.invoke({"thread_id": "persisted-thread", "incoming_message": "1990-05-10"}, config)

    assert "date of birth" in second_result["response_text"].lower()
    assert final_result["verified"] is True
    assert len(final_result["listed_appointments"]) == 2
