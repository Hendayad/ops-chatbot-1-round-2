import streamlit as st
import requests

from components.styles import page_header, role_badge_html

BASE_URL = "http://127.0.0.1:8000/api/v1"


def show_users():

    page_header(
        "👥", "User Management",
        subtitle="View learners and staff, and update their access role.",
        eyebrow="Admin",
    )

    try:
        with st.spinner("Loading users..."):
            response = requests.get(
                f"{BASE_URL}/users",
                headers={"Authorization": f"Bearer {st.session_state.token}"},
            )
    except requests.RequestException as e:
        st.error(f"Couldn't reach the backend: {e}")
        return

    if response.status_code != 200:
        st.error("Unauthorized")
        return

    users = response.json()

    if not users:
        st.info("No users found.")
        return

    for user in users:

        with st.container(border=True):

            info_col, role_col, action_col = st.columns([3, 2, 1])

            with info_col:
                st.write(f"**{user['email']}**")
                st.markdown(role_badge_html(user["role"]), unsafe_allow_html=True)

            with role_col:
                new_role = st.selectbox(
                    "Change role",
                    ["LEARNER", "ADMIN"],
                    index=["LEARNER", "ADMIN"].index(user["role"])
                    if user["role"] in ("LEARNER", "ADMIN")
                    else 0,
                    key=user["id"],
                    label_visibility="collapsed",
                )

            with action_col:
                unchanged = new_role == user["role"]
                if st.button(
                    "Update",
                    key=f"btn_{user['id']}",
                    use_container_width=True,
                    disabled=unchanged,
                ):
                    try:
                        with st.spinner("Updating role..."):
                            patch_response = requests.patch(
                                f"{BASE_URL}/users/{user['id']}/role",
                                json={"role": new_role},
                                headers={
                                    "Authorization": f"Bearer {st.session_state.token}"
                                },
                            )
                        if patch_response.status_code == 200:
                            st.success(f"Updated {user['email']} to {new_role}.")
                            st.rerun()
                        else:
                            st.error("Couldn't update the role. Please try again.")
                    except requests.RequestException as e:
                        st.error(f"Couldn't reach the backend: {e}")