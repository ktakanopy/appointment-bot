from app.graph.builder import build_graph


def test_confirm_flow_resolves_first_appointment_and_is_idempotent():
    graph = build_graph()
    config = {"configurable": {"thread_id": "graph-confirm"}}

    for message in [
        "show me my appointments",
        "Ana Silva",
        "11999998888",
        "1990-05-10",
    ]:
        graph.invoke({"thread_id": "graph-confirm", "incoming_message": message}, config)

    confirmed = graph.invoke({"thread_id": "graph-confirm", "incoming_message": "confirm the first one"}, config)
    confirmed_again = graph.invoke({"thread_id": "graph-confirm", "incoming_message": "confirm the first one"}, config)

    assert confirmed["last_action_result"]["outcome"] == "confirmed"
    assert confirmed_again["last_action_result"]["outcome"] == "already_confirmed"


def test_confirm_flow_resolves_date_reference_after_listing():
    graph = build_graph()
    config = {"configurable": {"thread_id": "graph-confirm-date"}}

    for message in [
        "show me my appointments, I'm Ana Silva",
        "11999998888",
        "1990-05-10",
    ]:
        graph.invoke({"thread_id": "graph-confirm-date", "incoming_message": message}, config)

    confirmed = graph.invoke(
        {"thread_id": "graph-confirm-date", "incoming_message": "confirm my 2026-04-20 appointment"},
        config,
    )

    assert confirmed["last_action_result"]["outcome"] == "confirmed"
