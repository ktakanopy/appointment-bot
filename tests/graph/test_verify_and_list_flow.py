from app.graph.builder import build_graph


def test_verify_then_list_flow_resumes_deferred_action():
    graph = build_graph()
    config = {"configurable": {"thread_id": "graph-verify-list"}}

    first = graph.invoke({"thread_id": "graph-verify-list", "incoming_message": "I want to see my appointments"}, config)
    second = graph.invoke({"thread_id": "graph-verify-list", "incoming_message": "Ana Silva"}, config)
    third = graph.invoke({"thread_id": "graph-verify-list", "incoming_message": "11999998888"}, config)
    final = graph.invoke({"thread_id": "graph-verify-list", "incoming_message": "1990-05-10"}, config)

    assert first["response_text"].startswith("I can help with that")
    assert second["response_text"].startswith("Thanks. What phone number")
    assert third["response_text"].startswith("Thanks. What is your date of birth")
    assert final["verified"] is True
    assert final["requested_action"] == "list_appointments"
    assert len(final["listed_appointments"]) == 2
    assert "Here are your appointments" in final["response_text"]


def test_greeting_routes_into_verification_before_help():
    graph = build_graph()
    config = {"configurable": {"thread_id": "graph-greeting-verify"}}

    result = graph.invoke({"thread_id": "graph-greeting-verify", "incoming_message": "hello"}, config)

    assert result["requested_action"] == "verify_identity"
    assert "full name" in result["response_text"].lower()
