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
    if response.get("response"):
        st.session_state.messages.append({"role": "assistant", "content": response["response"]})


def _handle_user_message(message: str) -> None:
    st.session_state.messages.append({"role": "user", "content": message})
    try:
        response = st.session_state.client.send_message(
            session_id=st.session_state.session_id,
            message=message,
            remembered_identity_id=st.session_state.remembered_identity_id,
        )
    except httpx.HTTPError as error:
        st.session_state.error = str(error)
        return
    st.session_state.messages.append({"role": "assistant", "content": response["response"]})
    st.session_state.verified = response["verified"]
    st.session_state.appointments = response.get("appointments") or []
    st.session_state.last_action_result = response.get("last_action_result")
    st.session_state.remembered_identity_status = response["remembered_identity_status"]
    st.session_state.remembered_identity_id = response["remembered_identity_status"]["remembered_identity_id"] or None
    st.session_state.error = response.get("error_code")


def _forget_identity() -> None:
    if not st.session_state.remembered_identity_id:
        return
    st.session_state.client.forget_remembered_identity(st.session_state.remembered_identity_id)
    st.session_state.remembered_identity_status = {
        "remembered_identity_id": st.session_state.remembered_identity_id,
        "status": "revoked",
    }
    st.session_state.remembered_identity_id = None


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

    message = st.chat_input("Ask about your appointments")
    if message:
        _handle_user_message(message)
        st.rerun()


if __name__ == "__main__":
    main()
