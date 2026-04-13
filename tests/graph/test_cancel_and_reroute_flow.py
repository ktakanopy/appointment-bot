from app.graph.builder import build_graph


def test_cancel_then_reroute_back_to_list():
    graph = build_graph()
    config = {"configurable": {"thread_id": "graph-cancel"}}

    for message in [
        "show me my appointments",
        "Ana Silva",
        "11999998888",
        "1990-05-10",
    ]:
        graph.invoke({"thread_id": "graph-cancel", "incoming_message": message}, config)

    canceled = graph.invoke({"thread_id": "graph-cancel", "incoming_message": "cancel the first one"}, config)
    refreshed = graph.invoke({"thread_id": "graph-cancel", "incoming_message": "show me my appointments again"}, config)

    assert canceled["last_action_result"]["outcome"] == "canceled"
    assert refreshed["requested_action"] == "list_appointments"
    assert refreshed["listed_appointments"][0].status.value == "canceled"
