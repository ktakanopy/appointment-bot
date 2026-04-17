from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from langgraph.graph import END
from langgraph.types import Command

from app.graph.parsing import (
    extract_appointment_reference,
    extract_dob,
    extract_full_name,
    extract_phone,
    resolve_appointment_reference,
)
from app.ports import LLMProvider
from app.graph.state import (
    AppointmentState,
    ConversationGraphState,
    TurnState,
    VerificationState,
    appointment_state,
    latest_user_message,
    serialize_messages,
    turn_state,
    verification_state,
)
from app.models import (
    ActionOutcome,
    Appointment,
    AppointmentNotCancelableError,
    AppointmentNotConfirmableError,
    AppointmentNotFoundError,
    AppointmentNotOwnedError,
    ConversationOperation,
    ConversationOperationResult,
    DateOfBirth,
    DependencyUnavailableError,
    FullName,
    Phone,
    TurnIssue,
    VerificationStatus,
)
from app.observability import log_event, record_node_trace
from app.services import AppointmentService, VerificationService

APPOINTMENT_ACTIONS = {
    ConversationOperation.CONFIRM_APPOINTMENT,
    ConversationOperation.CANCEL_APPOINTMENT,
}

MESSAGE_HISTORY_LIMIT = 6

INVALID_RESPONSES = {
    "full_name": TurnIssue.INVALID_FULL_NAME,
    "phone": TurnIssue.INVALID_PHONE,
    "dob": TurnIssue.INVALID_DOB,
}


def make_ingest_node(logger):
    """
    Build the graph node responsible for turn initialization.

    At this stage the current user message is already part of the `messages`
    channel because LangGraph merged the new input through the message reducer.
    This node only clears per-turn output fields so later nodes work with a
    clean response surface.
    """

    def ingest(state: ConversationGraphState) -> dict[str, dict]:
        turn = _reset_turn_output(turn_state(state))
        updated_state = {**state, "turn": turn.model_dump()}
        log_event(logger, "ingest", updated_state)
        record_node_trace(
            logger,
            getattr(logger, "tracer", None),
            node="ingest",
            state_before=state,
            state_after=updated_state,
        )
        return {"turn": turn.model_dump()}

    return ingest


def make_interpret_node(logger, provider: LLMProvider):
    """
    Build the node that maps the latest user message into structured intent.

    The node reads the latest user turn from the LangGraph message channel,
    prepares a bounded conversational context for the provider, merges any
    extracted identity fields into verification state, and decides whether the
    graph should continue into verification or move directly to action
    execution.
    """

    def interpret(
        state: ConversationGraphState,
    ) -> Command[Literal["verify", "execute_action"]]:
        message = latest_user_message(state)
        verification = verification_state(state)
        turn = turn_state(state)
        appointments = appointment_state(state)
        provider_state = {
            "verification": {"verified": verification.verified},
            "turn": {
                "requested_operation": turn.requested_operation.value,
            },
            "missing_verification_fields": verification.missing_fields(),
            "messages": serialize_messages(
                state.get("messages", []), MESSAGE_HISTORY_LIMIT
            ),
        }
        # The provider gets a deliberately small context object: enough to infer
        # the next action and missing identity fields, but not enough authority
        # to make verification or mutation decisions itself.
        try:
            result = provider.interpret(message, provider_state)
        except Exception as exc:
            log_event(
                logger,
                "interpret",
                state,
                outcome="provider_failed",
                error_type=type(exc).__name__,
            )
            raise DependencyUnavailableError("provider interpret failed") from exc
        log_event(logger, "interpret", state, outcome="provider_ok")
        # get from llm or try deterministic reference
        full_name = FullName.try_parse(result.full_name) or extract_full_name(message)
        phone = Phone.try_parse(result.phone) or extract_phone(message)
        dob = DateOfBirth.try_parse(result.dob) or extract_dob(message)
        # get from llm or try deterministic reference
        appointment_reference = (
            result.appointment_reference or extract_appointment_reference(message)
        )
        requested_operation = result.requested_operation
        updated_verification = _fill_missing_fields(
            verification,
            full_name=full_name,
            phone=phone,
            dob=dob,
        )
        updated_turn = turn.model_copy(update={"requested_operation": requested_operation})
        updated_appointments = _update_appointment_reference(
            appointments, requested_operation, appointment_reference
        )
        updates = {
            "verification": updated_verification.model_dump(),
            "turn": updated_turn.model_dump(),
            "appointments": updated_appointments.model_dump(),
        }
        next_state = {**state, **updates}
        log_event(
            logger,
            "interpret",
            next_state,
            appointment_reference=updated_appointments.appointment_reference,
        )
        # Routing happens immediately after interpretation. From this point on,
        # the flow is deterministic again.
        goto = "verify" if verification_required(next_state) else "execute_action"
        record_node_trace(
            logger,
            getattr(logger, "tracer", None),
            node="interpret",
            state_before=state,
            state_after=next_state,
            extra={
                "provider_result": result.model_dump(mode="json"),
                "goto": goto,
                "routing": {
                    "decision": "verification_required",
                    "chosen_next": goto,
                    "requested_operation": updated_turn.requested_operation,
                    "verified": updated_verification.verified,
                    "missing_verification_fields": updated_verification.missing_fields(),
                },
            },
        )
        return Command(update=updates, goto=goto)

    return interpret


def make_verification_node(
    verification_service: VerificationService, logger, max_verification_attempts: int
):
    """
    Build the node that owns the identity-verification lifecycle.

    This node is the gatekeeper for protected actions. It collects missing
    identity fields, checks the completed identity payload against the patient
    repository, and records failed attempts.
    """

    def verify(
        state: ConversationGraphState,
    ) -> Command[Literal["execute_action", "__end__"]]:
        verification = verification_state(state)
        turn = turn_state(state)
        if not verification_required(state):
            return Command(update={}, goto="execute_action")
        if verification.verification_status == VerificationStatus.LOCKED:
            updates = _set_locked_response(turn)
            next_state = {**state, **updates}
            log_event(logger, "verify", next_state, outcome="locked")
            record_node_trace(
                logger,
                getattr(logger, "tracer", None),
                node="verify",
                state_before=state,
                state_after=next_state,
                extra={"outcome": "locked"},
            )
            return Command(update=updates, goto=END)

        previous_status = verification.verification_status
        missing_field = verification.next_missing_field()
        if missing_field is not None:
            # Keep verification conversational by asking only for the next
            # missing field instead of resetting the whole identity flow.
            updates = _collect_missing_field(
                verification,
                turn,
                field_name=missing_field,
                previous_status=previous_status,
                state=state,
            )
            next_state = {**state, **updates}
            log_event(logger, "verify", next_state, outcome="collect_missing_field")
            record_node_trace(
                logger,
                getattr(logger, "tracer", None),
                node="verify",
                state_before=state,
                state_after=next_state,
                extra={
                    "outcome": "collect_missing_field",
                    "missing_field": missing_field,
                },
            )
            return Command(update=updates, goto=END)

        patient = verification_service.verify_identity(
            verification.provided_full_name,
            verification.provided_phone,
            verification.provided_dob,
        )
        if patient is None:
            updates, outcome = _handle_failed_verification(
                verification,
                turn,
                max_verification_attempts=max_verification_attempts,
            )
            next_state = {**state, **updates}
            log_event(logger, "verify", next_state, outcome=outcome)
            goto = END if should_skip_action_execution(next_state) else "execute_action"
            record_node_trace(
                logger,
                getattr(logger, "tracer", None),
                node="verify",
                state_before=state,
                state_after=next_state,
                extra={
                    "outcome": outcome,
                    "goto": "__end__" if goto == END else goto,
                    "routing": {
                        "decision": "should_skip_action_execution",
                        "chosen_next": "__end__" if goto == END else goto,
                        "outcome": outcome,
                    },
                },
            )
            return Command(update=updates, goto=goto)

        # A successful match does not immediately perform confirm/cancel. The
        # workflow always lands on list_appointments first so the patient has a
        # visible, stable appointment context for follow-up actions.
        updates = _handle_successful_verification(
            verification, turn, patient_id=patient.id
        )
        next_state = {**state, **updates}
        log_event(logger, "verify", next_state, outcome="verified")
        goto = END if should_skip_action_execution(next_state) else "execute_action"
        record_node_trace(
            logger,
            getattr(logger, "tracer", None),
            node="verify",
            state_before=state,
            state_after=next_state,
            extra={
                "outcome": "verified",
                "goto": "__end__" if goto == END else goto,
                "routing": {
                    "decision": "should_skip_action_execution",
                    "chosen_next": "__end__" if goto == END else goto,
                    "outcome": "verified",
                },
            },
        )
        return Command(update=updates, goto=goto)

    return verify


def make_list_node(appointment_service: AppointmentService, logger):
    """
    Build the node that lists appointments for the verified patient.

    Once verification is complete and the requested operation is
    `LIST_APPOINTMENTS`, this node loads the current appointment list, caches it
    for future reference resolution, and stamps the turn as a successful list
    response.
    """

    def list_appointments(
        state: ConversationGraphState,
    ) -> dict[str, dict]:
        verification = verification_state(state)
        turn = turn_state(state)
        appointments = appointment_service.list_appointments(verification.patient_id)
        updated_appointments = AppointmentState(
            listed_appointments=appointments,
            appointment_reference=appointment_state(state).appointment_reference,
        )
        updated_turn = turn.model_copy(update={
            "requested_operation": ConversationOperation.LIST_APPOINTMENTS,
            "operation_result": ConversationOperationResult(
                operation=ConversationOperation.LIST_APPOINTMENTS,
                outcome=ActionOutcome.LISTED,
            ),
            "issue": None,
        })
        updates = {
            "appointments": updated_appointments.model_dump(),
            "turn": updated_turn.model_dump(),
        }
        log_event(
            logger,
            "list_appointments",
            {**state, **updates},
            appointment_count=len(appointments),
        )
        record_node_trace(
            logger,
            getattr(logger, "tracer", None),
            node="list_appointments",
            state_before=state,
            state_after={**state, **updates},
            extra={"appointment_count": len(appointments)},
        )
        return updates

    return list_appointments


def make_confirm_node(appointment_service: AppointmentService, logger):
    """
    Build the confirm-action node.

    Confirming and canceling share the same skeleton: resolve a target
    appointment, call the service mutation, translate domain failures into
    turn-level responses, refresh the cached list, and emit telemetry. This
    wrapper keeps the confirm-specific details explicit while delegating the
    common mechanics.
    """

    def confirm_appointment(
        state: ConversationGraphState,
    ) -> dict[str, dict]:
        return _execute_appointment_mutation(
            state,
            appointment_service,
            logger,
            operation=ConversationOperation.CONFIRM_APPOINTMENT,
            mutate_appointment=appointment_service.confirm_appointment,
            not_allowed_error=AppointmentNotConfirmableError,
            not_allowed_issue=TurnIssue.APPOINTMENT_NOT_CONFIRMABLE,
            not_allowed_outcome="not_confirmable",
            already_done_outcome=ActionOutcome.ALREADY_CONFIRMED,
            event_name="confirm_appointment",
        )

    return confirm_appointment


def make_cancel_node(appointment_service: AppointmentService, logger):
    """
    Build the cancel-action node.

    This wrapper keeps cancel as a first-class business action while still
    sharing the generic mutation workflow used by confirm. The cancel-specific
    response keys and allowed-error semantics stay visible at the call site.
    """

    def cancel_appointment(
        state: ConversationGraphState,
    ) -> dict[str, dict]:
        return _execute_appointment_mutation(
            state,
            appointment_service,
            logger,
            operation=ConversationOperation.CANCEL_APPOINTMENT,
            mutate_appointment=appointment_service.cancel_appointment,
            not_allowed_error=AppointmentNotCancelableError,
            not_allowed_issue=TurnIssue.APPOINTMENT_NOT_CANCELABLE,
            not_allowed_outcome="not_cancelable",
            already_done_outcome=ActionOutcome.ALREADY_CANCELED,
            event_name="cancel_appointment",
        )

    return cancel_appointment


def make_help_node(logger):
    """
    Build the fallback node for help and unsupported requests.

    When the graph does not need to execute a protected appointment action, it
    routes here to produce a helpful response that still respects whether the
    user has already been verified.
    """

    def help_or_unknown(state: ConversationGraphState) -> dict[str, dict]:
        updated_turn = turn_state(state).model_copy(
            update={
                "requested_operation": ConversationOperation.HELP,
                "issue": None,
                "operation_result": None,
            }
        )
        updates = {"turn": updated_turn.model_dump()}
        log_event(logger, "help_or_unknown", {**state, **updates})
        record_node_trace(
            logger,
            getattr(logger, "tracer", None),
            node="help_or_unknown",
            state_before=state,
            state_after={**state, **updates},
        )
        return updates

    return help_or_unknown


def make_execute_action_node(
    logger,
    *,
    list_node: Callable[[ConversationGraphState], dict[str, dict]],
    confirm_node: Callable[[ConversationGraphState], dict[str, dict]],
    cancel_node: Callable[[ConversationGraphState], dict[str, dict]],
    help_node: Callable[[ConversationGraphState], dict[str, dict]],
):
    """
    Build the dispatcher that executes the concrete business action.

    After interpretation and, when needed, verification, the graph reaches this
    node with a single requested operation that acts as the source of truth for
    which business action should run.
    """

    def execute_action(
        state: ConversationGraphState,
    ) -> dict[str, dict]:
        if should_skip_action_execution(state):
            # Verification can already produce the full turn result. In that
            # case there is nothing left for the action dispatcher to do.
            log_event(logger, "execute_action", state, outcome="skipped")
            record_node_trace(
                logger,
                getattr(logger, "tracer", None),
                node="execute_action",
                state_before=state,
                state_after=state,
                extra={"outcome": "skipped"},
            )
            return {}
        operation = turn_state(state).requested_operation
        if operation == ConversationOperation.LIST_APPOINTMENTS:
            return list_node(state)
        if operation == ConversationOperation.CONFIRM_APPOINTMENT:
            return confirm_node(state)
        if operation == ConversationOperation.CANCEL_APPOINTMENT:
            return cancel_node(state)
        return help_node(state)

    return execute_action


def _update_appointment_reference(
    appointments: AppointmentState,
    requested_operation: ConversationOperation,
    appointment_reference: str | None,
) -> AppointmentState:
    # Only confirm/cancel should carry appointment targeting context across the
    # turn boundary. Listing or help requests clear it.
    if requested_operation not in APPOINTMENT_ACTIONS:
        return appointments.model_copy(update={"appointment_reference": None})
    if appointment_reference:
        return appointments.model_copy(update={"appointment_reference": appointment_reference})
    return appointments


def _execute_appointment_mutation(
    state: ConversationGraphState,
    appointment_service: AppointmentService,
    logger,
    *,
    operation: ConversationOperation,
    mutate_appointment: Callable[[str | None, str], tuple[Appointment, ActionOutcome]],
    not_allowed_error: type[Exception],
    not_allowed_issue: TurnIssue,
    not_allowed_outcome: str,
    already_done_outcome: ActionOutcome,
    event_name: str,
) -> dict[str, dict]:
    verification = verification_state(state)
    appointments = appointment_state(state)
    turn = turn_state(state)
    # Both confirm and cancel follow the same sequence:
    # 1. resolve a single target appointment
    # 2. run the service mutation
    # 3. translate domain errors into turn issues
    # 4. refresh the cached appointment list for the next turn
    appointment, resolve_updates = _resolve_target_appointment(
        state,
        appointment_service,
        operation=operation,
    )
    if appointment is None:
        log_event(
            logger,
            "resolve_appointment_reference",
            {**state, **resolve_updates},
            outcome=turn_state({"turn": resolve_updates["turn"]}).issue.value,
        )
        record_node_trace(
            logger,
            getattr(logger, "tracer", None),
            node="resolve_appointment_reference",
            state_before=state,
            state_after={**state, **resolve_updates},
            extra={"outcome": turn_state({"turn": resolve_updates["turn"]}).issue.value},
        )
        return resolve_updates

    try:
        updated, outcome = mutate_appointment(
            verification.patient_id, appointment.id
        )
    except not_allowed_error:
        updated_turn = turn.model_copy(
            update={
                "requested_operation": operation,
                "issue": not_allowed_issue,
                "operation_result": None,
            }
        )
        updates = {"turn": updated_turn.model_dump()}
        log_event(logger, event_name, {**state, **updates}, outcome=not_allowed_outcome)
        record_node_trace(
            logger,
            getattr(logger, "tracer", None),
            node=event_name,
            state_before=state,
            state_after={**state, **updates},
            extra={"outcome": not_allowed_outcome},
        )
        return updates
    except AppointmentNotOwnedError:
        updated_turn = turn.model_copy(
            update={
                "requested_operation": operation,
                "issue": TurnIssue.APPOINTMENT_NOT_OWNED,
                "operation_result": None,
            }
        )
        updates = {"turn": updated_turn.model_dump()}
        log_event(logger, event_name, {**state, **updates}, outcome="not_owned")
        record_node_trace(
            logger,
            getattr(logger, "tracer", None),
            node=event_name,
            state_before=state,
            state_after={**state, **updates},
            extra={"outcome": "not_owned"},
        )
        return updates
    except AppointmentNotFoundError:
        updated_turn = turn.model_copy(
            update={
                "requested_operation": operation,
                "issue": TurnIssue.APPOINTMENT_NOT_FOUND,
                "operation_result": None,
            }
        )
        updates = {"turn": updated_turn.model_dump()}
        log_event(logger, event_name, {**state, **updates}, outcome="not_found")
        record_node_trace(
            logger,
            getattr(logger, "tracer", None),
            node=event_name,
            state_before=state,
            state_after={**state, **updates},
            extra={"outcome": "not_found"},
        )
        return updates

    updated_turn = turn.model_copy(update={
        "requested_operation": operation,
        "issue": None,
        "operation_result": ConversationOperationResult(
            operation=operation,
            outcome=outcome,
            appointment_id=appointment.id,
        ),
    })
    updated_appointments = appointments.model_copy(update={
        "listed_appointments": appointment_service.list_appointments(
            verification.patient_id
        ),
    })
    updates = {
        "turn": updated_turn.model_dump(),
        "appointments": updated_appointments.model_dump(),
    }
    log_event(
        logger,
        event_name,
        {**state, **updates},
        outcome=outcome.value,
        appointment_id=appointment.id,
    )
    record_node_trace(
        logger,
        getattr(logger, "tracer", None),
        node=event_name,
        state_before=state,
        state_after={**state, **updates},
        extra={"outcome": outcome.value, "appointment_id": appointment.id},
    )
    return updates


def _set_locked_response(turn: TurnState) -> dict[str, dict]:
    updated_turn = turn.model_copy(
        update={
            "requested_operation": ConversationOperation.VERIFY_IDENTITY,
            "issue": TurnIssue.VERIFICATION_LOCKED,
            "operation_result": None,
        }
    )
    return {"turn": updated_turn.model_dump()}


def _collect_missing_field(
    verification: VerificationState,
    turn: TurnState,
    *,
    field_name: str,
    previous_status: VerificationStatus,
    state: ConversationGraphState,
) -> dict[str, dict]:
    updated_verification = verification.model_copy(
        update={"verification_status": VerificationStatus.COLLECTING}
    )
    # Invalid field feedback is attached to the current turn, but the partially
    # collected identity values stay in verification state so the user can retry
    # without losing prior valid inputs.
    invalid_issue = _invalid_issue_for_field(state, field_name, previous_status)
    updated_turn = turn.model_copy(
        update={
            "requested_operation": ConversationOperation.VERIFY_IDENTITY,
            "issue": invalid_issue,
            "operation_result": None,
        }
    )
    return {
        "verification": updated_verification.model_dump(),
        "turn": updated_turn.model_dump(),
    }


def _handle_failed_verification(
    verification: VerificationState,
    turn: TurnState,
    *,
    max_verification_attempts: int,
) -> tuple[dict[str, dict], str]:
    failures = verification.verification_failures + 1
    updated_verification = verification.model_copy(
        update={
            "verification_failures": failures,
            "verification_status": VerificationStatus.FAILED,
            "verified": False,
            "patient_id": None,
            "provided_full_name": None,
            "provided_phone": None,
            "provided_dob": None,
        }
    )
    # A full identity mismatch resets collected identity fields. That prevents
    # the next attempt from accidentally mixing data from two different people.
    if failures >= max_verification_attempts:
        updated_verification = updated_verification.model_copy(
            update={"verification_status": VerificationStatus.LOCKED}
        )
        updates = {
            "verification": updated_verification.model_dump(),
            **_set_locked_response(turn),
        }
        return updates, "locked"
    updated_turn = turn.model_copy(
        update={
            "requested_operation": ConversationOperation.VERIFY_IDENTITY,
            "issue": TurnIssue.INVALID_IDENTITY,
            "operation_result": None,
        }
    )
    return {
        "verification": updated_verification.model_dump(),
        "turn": updated_turn.model_dump(),
    }, "failed"


def _handle_successful_verification(
    verification: VerificationState,
    turn: TurnState,
    *,
    patient_id: str,
) -> dict[str, dict]:
    updated_verification = verification.model_copy(
        update={
            "verification_status": VerificationStatus.VERIFIED,
            "verified": True,
            "verification_failures": 0,
            "patient_id": patient_id,
        }
    )
    updated_turn = turn.model_copy(
        update={
            "requested_operation": ConversationOperation.LIST_APPOINTMENTS,
            "issue": None,
            "operation_result": None,
        }
    )
    return {
        "verification": updated_verification.model_dump(),
        "turn": updated_turn.model_dump(),
    }


def _invalid_issue_for_field(
    state: ConversationGraphState,
    field_name: str,
    previous_status: VerificationStatus,
) -> TurnIssue | None:
    if previous_status not in {
        VerificationStatus.COLLECTING,
        VerificationStatus.FAILED,
    }:
        return None
    message = latest_user_message(state)
    if not message:
        return None
    parsed_name = extract_full_name(message)
    parsed_phone = extract_phone(message)
    parsed_dob = extract_dob(message)
    if (
        field_name == "full_name"
        and parsed_name is None
        and parsed_phone is None
        and parsed_dob is None
    ):
        return INVALID_RESPONSES[field_name]
    if (
        field_name == "phone"
        and parsed_phone is None
        and parsed_name is None
        and parsed_dob is None
    ):
        return INVALID_RESPONSES[field_name]
    if (
        field_name == "dob"
        and parsed_dob is None
        and parsed_name is None
        and parsed_phone is None
    ):
        return INVALID_RESPONSES[field_name]
    return None


def _resolve_target_appointment(
    state: ConversationGraphState,
    appointment_service: AppointmentService,
    *,
    operation: ConversationOperation,
) -> tuple[Appointment | None, dict[str, dict]]:
    """pick the single appointment for confirm or cancel using state and services.

    reads appointment_reference from graph state (set during interpretation)
    and resolves it against a candidate list. if the user gave a numeric index
    (e.g. "1" for "the first one") but there is no in-session list from a prior
    list_appointments turn, resolution cannot proceed: returns (none, turn
    update) with missing_list_context so the assistant can ask them to list
    first.

    otherwise builds appointment_options from the cached list when present,
    or falls back to the patient's current appointments from the repository so
    id and date references still work after verification without requiring a
    prior list.

    delegates matching to resolve_appointment_reference. if that returns none
    (missing reference, no match, duplicate dates, or out-of-range index),
    returns (none, turn update) with ambiguous_appointment_reference and the
    caller-specific ambiguous_key for the user-facing message.

    returns (appointment, {}) on success; the empty dict means no partial
    state merge is needed beyond the mutation node itself.
    """
    appointments = appointment_state(state)
    turn = turn_state(state)
    verification = verification_state(state)
    listed_appointments = appointments.listed_appointments or []
    reference = appointments.appointment_reference

    # ordinal-style references only make sense relative to a list the user saw.
    if reference and reference.isdigit() and not listed_appointments:
        return None, {
            "turn": turn.model_copy(
                update={
                    "requested_operation": operation,
                    "issue": TurnIssue.MISSING_LIST_CONTEXT,
                    "operation_result": None,
                }
            ).model_dump()
        }

    # prefer the session cache; otherwise load fresh appointments for id/date resolution.
    appointment_options = listed_appointments or appointment_service.list_appointments(
        verification.patient_id
    )
    appointment = resolve_appointment_reference(reference, appointment_options)

    # any failure to pin down exactly one appointment is surfaced as ambiguous for this turn.
    if appointment is None:
        return None, {
            "turn": turn.model_copy(
                update={
                    "requested_operation": operation,
                    "issue": TurnIssue.AMBIGUOUS_APPOINTMENT_REFERENCE,
                    "operation_result": None,
                }
            ).model_dump()
        }
    return appointment, {}


def _fill_missing_fields(
    verification: VerificationState,
    *,
    full_name: str | None,
    phone: str | None,
    dob: str | None,
    ) -> VerificationState:
    updates = {}
    if verification.provided_full_name is None and full_name:
        updates["provided_full_name"] = full_name
    if verification.provided_phone is None and phone:
        updates["provided_phone"] = phone
    if verification.provided_dob is None and dob:
        updates["provided_dob"] = dob
    return verification.model_copy(update=updates)


def _reset_turn_output(turn: TurnState) -> TurnState:
    return turn.model_copy(update={"issue": None, "operation_result": None})


def verification_required(state: ConversationGraphState) -> bool:
    operation = turn_state(state).requested_operation
    verification = verification_state(state)
    return bool(
        not verification.verified
        and (operation.requires_verification or operation.triggers_verification_flow)
    )


def should_skip_action_execution(state: ConversationGraphState) -> bool:
    return turn_state(state).has_turn_output()
