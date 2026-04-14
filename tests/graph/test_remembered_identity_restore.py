from __future__ import annotations

from app.graph.builder import build_graph


def test_graph_allows_list_action_when_session_bootstraps_verified_patient():
    graph = build_graph()
    config = {"configurable": {"thread_id": "graph-remembered-restore"}}

    result = graph.invoke(
        {
            "thread_id": "graph-remembered-restore",
            "incoming_message": "show my appointments",
            "verified": True,
            "verification_status": "verified",
            "patient_id": "p1",
            "remembered_identity_id": "rid-1",
        },
        config,
    )

    assert result["verified"] is True
    assert result["requested_action"] == "list_appointments"
    assert len(result["listed_appointments"]) == 2
