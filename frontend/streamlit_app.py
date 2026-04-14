from __future__ import annotations

import httpx
import streamlit as st

from app.config import load_settings
from frontend.lib.api_client import BackendClient


def _client() -> BackendClient:
    return BackendClient(load_settings().frontend_api_base_url)


def _ensure_state() -> None:
    if "client" not in st.session_state:
        st.session_state.client = _client()
    if "session_id" not in st.session_state:
        st.session_state.session_id = None
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = None
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "verified" not in st.session_state:
        st.session_state.verified = False
    if "appointments" not in st.session_state:
        st.session_state.appointments = []
    if "last_action_result" not in st.session_state:
        st.session_state.last_action_result = None
    if "remembered_identity_id" not in st.session_state:
        st.session_state.remembered_identity_id = None
    if "remembered_identity_status" not in st.session_state:
        st.session_state.remembered_identity_status = {"remembered_identity_id": "", "status": "unavailable"}
    if "error" not in st.session_state:
        st.session_state.error = None
    if "current_action" not in st.session_state:
        st.session_state.current_action = "verify_identity"


def _start_session(remembered_identity_id: str | None = None) -> None:
    response = st.session_state.client.create_session(remembered_identity_id=remembered_identity_id)
    st.session_state.session_id = response["session_id"]
    st.session_state.thread_id = response["thread_id"]
    st.session_state.verified = response["restored_verification"]
    st.session_state.messages = []
    st.session_state.appointments = []
    st.session_state.last_action_result = None
    st.session_state.remembered_identity_status = response["remembered_identity_status"]
    st.session_state.remembered_identity_id = response["remembered_identity_status"]["remembered_identity_id"] or None
    st.session_state.error = None
    st.session_state.current_action = "help" if response["restored_verification"] else "verify_identity"
    if response.get("response"):
        st.session_state.messages.append({"role": "assistant", "content": response["response"]})


def _handle_user_message(message: str) -> None:
    st.session_state.messages.append({"role": "user", "content": message})
    streamed_response = None
    status_placeholder = st.empty()
    assistant_placeholder = st.empty()
    try:
        with assistant_placeholder.container():
            with st.chat_message("assistant"):
                response_placeholder = st.empty()
                for event in st.session_state.client.send_message_stream(
                    session_id=st.session_state.session_id,
                    message=message,
                    remembered_identity_id=st.session_state.remembered_identity_id,
                ):
                    if event["event"] == "node":
                        status_placeholder.caption(_node_status_text(event["data"]))
                        continue
                    if event["event"] == "message":
                        streamed_response = event["data"]
                        response_placeholder.write(streamed_response["response"])
                        continue
                    if event["event"] == "error":
                        raise httpx.HTTPError(event["data"]["detail"])
    except httpx.HTTPError as error:
        st.session_state.error = str(error)
        return
    finally:
        status_placeholder.empty()
    if streamed_response is None:
        st.session_state.error = "No response received from the backend."
        return
    st.session_state.messages.append({"role": "assistant", "content": streamed_response["response"]})
    st.session_state.verified = streamed_response["verified"]
    st.session_state.appointments = streamed_response.get("appointments") or []
    st.session_state.last_action_result = streamed_response.get("last_action_result")
    st.session_state.remembered_identity_status = streamed_response["remembered_identity_status"]
    st.session_state.remembered_identity_id = streamed_response["remembered_identity_status"]["remembered_identity_id"] or None
    st.session_state.error = streamed_response.get("error_code")
    st.session_state.current_action = response.get("current_action", "unknown")


def _forget_identity() -> None:
    if not st.session_state.remembered_identity_id:
        return
    st.session_state.client.forget_remembered_identity(st.session_state.remembered_identity_id)
    st.session_state.remembered_identity_status = {
        "remembered_identity_id": st.session_state.remembered_identity_id,
        "status": "revoked",
    }
    st.session_state.remembered_identity_id = None


def _node_status_text(data: dict[str, str | bool | None]) -> str:
    node = data.get("node")
    if node == "verification_subgraph":
        return "Verifying identity..."
    if node in {"list_appointments", "confirm_appointment", "cancel_appointment"}:
        return "Applying appointment action..."
    if node == "generate_response":
        return "Preparing response..."
    return "Processing..."
    st.session_state.current_action = "verify_identity"


def _chat_placeholder() -> str:
    if st.session_state.current_action == "verify_identity" or not st.session_state.verified:
        return "Start by entering your full name"
    return "Ask about your appointments"


def _render_guidance() -> None:
    if st.session_state.current_action == "verify_identity" or not st.session_state.verified:
        st.info("Please identify yourself first. Start with your full name, then provide your phone number and date of birth.")
        return
    st.success("You are verified. You can ask me to list your appointments, confirm one, or cancel one.")


def main() -> None:
    st.set_page_config(page_title="Appointment Bot", page_icon=":hospital:")
    _ensure_state()

    st.title("Appointment Bot")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Start new session", use_container_width=True):
            _start_session(remembered_identity_id=st.session_state.remembered_identity_id)
    with col2:
        if st.button("Forget remembered identity", use_container_width=True):
            _forget_identity()

    st.write(f"Verified: {'yes' if st.session_state.verified else 'no'}")
    st.write(f"Remembered identity: {st.session_state.remembered_identity_status['status']}")
    _render_guidance()

    if st.session_state.appointments:
        st.subheader("Appointments")
        st.table(st.session_state.appointments)

    if st.session_state.last_action_result:
        st.subheader("Last action")
        st.json(st.session_state.last_action_result)

    if st.session_state.error:
        st.warning(str(st.session_state.error))

    for item in st.session_state.messages:
        with st.chat_message(item["role"]):
            st.write(item["content"])

    if st.session_state.session_id is None:
        _start_session(remembered_identity_id=st.session_state.remembered_identity_id)

    message = st.chat_input(_chat_placeholder())
    if message:
        _handle_user_message(message)
        st.rerun()


if __name__ == "__main__":
    main()
