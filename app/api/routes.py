from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.schemas import ActionResultResponse, AppointmentSummary, ChatRequest, ChatResponse
from app.domain.services import RepositoryUnavailableError
from app.graph.builder import build_graph

router = APIRouter()
graph = build_graph()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        result = graph.invoke(
            {
                "thread_id": request.session_id,
                "incoming_message": request.message,
            },
            {"configurable": {"thread_id": request.session_id}},
        )
    except RepositoryUnavailableError as error:
        raise HTTPException(status_code=503, detail="The appointment service is temporarily unavailable.") from error

    appointments = None
    if result.get("requested_action") == "list_appointments" and result.get("listed_appointments"):
        appointments = [
            AppointmentSummary(
                id=appointment.id,
                date=appointment.date,
                time=appointment.time,
                doctor=appointment.doctor,
                status=appointment.status.value,
            )
            for appointment in result["listed_appointments"]
        ]

    last_action_result = None
    if result.get("last_action_result"):
        last_action_result = ActionResultResponse(**result["last_action_result"])

    current_action = result.get("requested_action") or "unknown"
    if not result.get("verified") and current_action == "unknown":
        current_action = "verify_identity"

    return ChatResponse(
        response=result["response_text"],
        verified=result.get("verified", False),
        current_action=current_action,
        thread_id=request.session_id,
        appointments=appointments,
        last_action_result=last_action_result,
        error_code=result.get("error_code"),
    )
