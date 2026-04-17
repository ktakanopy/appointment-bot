from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from langchain_core.messages import AIMessage, AnyMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import MessagesState
from pydantic import BaseModel, ConfigDict, Field

from app.models import (
    Appointment,
    ConversationOperation,
    ConversationOperationResult,
    TurnIssue,
    VerificationStatus,
)


class ConversationGraphState(MessagesState):
    thread_id: str
    verification: dict[str, Any]
    turn: dict[str, Any]
    appointments: dict[str, Any]


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
        # Verification is intentionally progressive: we ask for one missing
        # field at a time instead of forcing the user to restate everything.
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
    operation_result: ConversationOperationResult | None = None
    issue: TurnIssue | None = None

    def has_turn_output(self) -> bool:
        return any(
            value is not None
            for value in (
                self.issue,
                self.operation_result,
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


def verification_state(state: ConversationGraphState | dict[str, Any]) -> VerificationState:
    """Read verification state from the LangGraph state dict as a typed model.

    LangGraph stores nested state as plain dicts and node updates can be
    partial — a node only returns the keys it changed. Calling model_validate
    against the raw dict (or an empty dict when the key is missing) fills in
    all defaults so callers always get a fully-typed object with no KeyError
    risk.
    """
    return VerificationState.model_validate(
        cast(dict[str, Any], state.get("verification", {}))
    )


def turn_state(state: ConversationGraphState | dict[str, Any]) -> TurnState:
    """Read per-turn state from the LangGraph state dict as a typed model.

    Same pattern as verification_state: the graph holds dicts, this reader
    gives nodes and helpers a typed surface to work with.
    """
    return TurnState.model_validate(cast(dict[str, Any], state.get("turn", {})))


def appointment_state(state: ConversationGraphState | dict[str, Any]) -> AppointmentState:
    """Read appointment state from the LangGraph state dict as a typed model.

    Same pattern as verification_state: the graph holds dicts, this reader
    gives nodes and helpers a typed surface to work with.
    """
    return AppointmentState.model_validate(
        cast(dict[str, Any], state.get("appointments", {}))
    )


def latest_user_message(state: ConversationGraphState) -> str:
    """Return the most recent human message text from the LangGraph message channel.

    LangGraph accumulates all messages in the channel across turns. Nodes only
    need the current user input, so we scan backwards and stop at the first
    HumanMessage instead of re-processing the full history.
    """
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
    # Convert the mutable graph snapshot into a typed object that the API,
    # response builder, and tests can read more comfortably.
    verification = verification_state(state)
    turn = turn_state(state)
    appointments = appointment_state(state)
    return ConversationState(
        thread_id=cast(str, state.get("thread_id", "")),
        messages=serialize_messages(cast(Sequence[AnyMessage], state.get("messages", []))),
        verification=verification,
        turn=turn,
        appointments=appointments,
    )


def _message_role(message: BaseMessage) -> str:
    if isinstance(message, HumanMessage):
        return "user"
    if isinstance(message, AIMessage):
        return "assistant"
    if isinstance(message, SystemMessage):
        return "system"
    return "assistant"


def _message_content(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    return str(content)
