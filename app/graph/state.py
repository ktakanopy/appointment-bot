from __future__ import annotations

from collections.abc import Sequence
from typing import Any, TypedDict, cast

from langchain_core.messages import AIMessage, AnyMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import MessagesState
from pydantic import BaseModel, ConfigDict, Field

from app.models import (
    Appointment,
    ConversationOperation,
    ConversationOperationResult,
    ResponseKey,
    TurnIssue,
    VerificationStatus,
)


class GraphVerificationState(TypedDict):
    verified: bool
    verification_failures: int
    verification_status: VerificationStatus
    patient_id: str | None
    provided_full_name: str | None
    provided_phone: str | None
    provided_dob: str | None


class GraphTurnState(TypedDict):
    requested_operation: ConversationOperation
    deferred_operation: ConversationOperation | None
    operation_result: ConversationOperationResult | None
    response_key: ResponseKey | None
    issue: TurnIssue | None
    subject_appointment: Appointment | None


class GraphAppointmentState(TypedDict):
    listed_appointments: list[Appointment]
    appointment_reference: str | None


class ConversationGraphState(MessagesState):
    thread_id: str
    verification: GraphVerificationState
    turn: GraphTurnState
    appointments: GraphAppointmentState


class ConversationGraphInput(MessagesState):
    thread_id: str


class VerificationState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    verified: bool = False
    verification_failures: int = 0
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    patient_id: str | None = None
    provided_full_name: str | None = None
    provided_phone: str | None = None
    provided_dob: str | None = None

    def missing_fields(self) -> list[str]:
        missing = []
        if not self.provided_full_name:
            missing.append("full_name")
        if not self.provided_phone:
            missing.append("phone")
        if not self.provided_dob:
            missing.append("dob")
        return missing

    def next_missing_field(self) -> str | None:
        missing = self.missing_fields()
        if not missing:
            return None
        return missing[0]


class TurnState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    requested_operation: ConversationOperation = ConversationOperation.UNKNOWN
    deferred_operation: ConversationOperation | None = None
    operation_result: ConversationOperationResult | None = None
    response_key: ResponseKey | None = None
    issue: TurnIssue | None = None
    subject_appointment: Appointment | None = None

    def has_turn_output(self) -> bool:
        return any(
            value is not None
            for value in (
                self.response_key,
                self.issue,
                self.operation_result,
                self.subject_appointment,
            )
        )


class AppointmentState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    listed_appointments: list[Appointment] = Field(default_factory=list)
    appointment_reference: str | None = None


class ConversationState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    thread_id: str = ""
    messages: list[dict[str, str]] = Field(default_factory=list)
    verification: VerificationState = Field(default_factory=VerificationState)
    turn: TurnState = Field(default_factory=TurnState)
    appointments: AppointmentState = Field(default_factory=AppointmentState)


def default_verification_state() -> GraphVerificationState:
    return {
        "verified": False,
        "verification_failures": 0,
        "verification_status": VerificationStatus.UNVERIFIED,
        "patient_id": None,
        "provided_full_name": None,
        "provided_phone": None,
        "provided_dob": None,
    }


def default_turn_state() -> GraphTurnState:
    return {
        "requested_operation": ConversationOperation.UNKNOWN,
        "deferred_operation": None,
        "operation_result": None,
        "response_key": None,
        "issue": None,
        "subject_appointment": None,
    }


def default_appointment_state() -> GraphAppointmentState:
    return {
        "listed_appointments": [],
        "appointment_reference": None,
    }


def verification_state(state: ConversationGraphState) -> GraphVerificationState:
    return {
        **default_verification_state(),
        **cast(dict[str, Any], state.get("verification", {})),
    }


def turn_state(state: ConversationGraphState) -> GraphTurnState:
    return {
        **default_turn_state(),
        **cast(dict[str, Any], state.get("turn", {})),
    }


def appointment_state(state: ConversationGraphState) -> GraphAppointmentState:
    return {
        **default_appointment_state(),
        **cast(dict[str, Any], state.get("appointments", {})),
    }


def latest_user_message(state: ConversationGraphState) -> str:
    for message in reversed(state.get("messages", [])):
        if isinstance(message, HumanMessage):
            return _message_content(message).strip()
    return ""


def serialize_messages(messages: Sequence[AnyMessage], limit: int | None = None) -> list[dict[str, str]]:
    selected_messages = list(messages[-limit:] if limit is not None else messages)
    return [
        {
            "role": _message_role(message),
            "content": _message_content(message),
        }
        for message in selected_messages
    ]


def build_conversation_state(state: ConversationGraphState | dict[str, Any]) -> ConversationState:
    verification = verification_state(state)
    turn = turn_state(state)
    appointments = appointment_state(state)
    return ConversationState(
        thread_id=cast(str, state.get("thread_id", "")),
        messages=serialize_messages(cast(Sequence[AnyMessage], state.get("messages", []))),
        verification=VerificationState.model_validate(verification),
        turn=TurnState.model_validate(turn),
        appointments=AppointmentState.model_validate(appointments),
    )


def _message_role(message: BaseMessage) -> str:
    if isinstance(message, HumanMessage):
        return "user"
    if isinstance(message, AIMessage):
        return "assistant"
    if isinstance(message, SystemMessage):
        return "system"
    if isinstance(message, ToolMessage):
        return "tool"
    return "assistant"


def _message_content(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    return str(content)
