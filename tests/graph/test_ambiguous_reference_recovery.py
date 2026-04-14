from app.graph.builder import build_graph


def test_confirm_ordinal_without_current_list_asks_for_list_first():
    graph = build_graph()
    config = {"configurable": {"thread_id": "graph-ambiguous"}}

    for message in [
        "Ana Silva",
        "11999998888",
        "1990-05-10",
    ]:
        graph.invoke({"thread_id": "graph-ambiguous", "incoming_message": message}, config)

    result = graph.invoke({"thread_id": "graph-ambiguous", "incoming_message": "confirm the first one"}, config)

    assert result["turn"]["error_code"] == "missing_list_context"
    assert "see your appointments first" in result["turn"]["response_text"]
