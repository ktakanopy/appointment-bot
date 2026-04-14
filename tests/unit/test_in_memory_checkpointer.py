from __future__ import annotations

from app.graph.builder import build_graph


def test_in_memory_checkpointer_preserves_thread_state_within_runtime():
    graph = build_graph()
    config = {"configurable": {"thread_id": "in-memory-thread"}}

    graph.invoke({"thread_id": "in-memory-thread", "incoming_message": "show my appointments"}, config)
    graph.invoke({"thread_id": "in-memory-thread", "incoming_message": "Ana Silva"}, config)
    second_result = graph.invoke({"thread_id": "in-memory-thread", "incoming_message": "11999998888"}, config)
    final_result = graph.invoke({"thread_id": "in-memory-thread", "incoming_message": "1990-05-10"}, config)

    assert "date of birth" in second_result["response_text"].lower()
    assert final_result["verified"] is True
    assert len(final_result["listed_appointments"]) == 2
