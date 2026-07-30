import streamlit as st

from components.styles import page_header, role_badge_html


def show_settings():

    page_header(
        "⚙️", "Settings",
        subtitle="Connection details and account information.",
    )

    col1, col2 = st.columns(2)

    with col1:
        with st.container(border=True):
            st.subheader("Backend")
            st.caption("API endpoint this app is connected to")
            st.code("http://127.0.0.1:8000/api/v1", language="text")

    with col2:
        with st.container(border=True):
            st.subheader("Account")
            user = st.session_state.get("user", {}) or {}
            st.write(user.get("email", "Authenticated"))
            st.markdown(
                role_badge_html(st.session_state.get("role", "")),
                unsafe_allow_html=True,
            )

    st.write("")

    if st.button("Logout", use_container_width=True):
        st.session_state.token = None
        st.session_state.role = None
        st.session_state.user = {}
        st.session_state.pop("messages", None)
        st.session_state.pop("history_loaded", None)
        st.rerun()