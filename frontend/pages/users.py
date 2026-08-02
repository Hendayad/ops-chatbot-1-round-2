import streamlit as st
import requests

from components.styles import page_header, role_badge_html

from api.config import BASE_URL

ROLE_OPTIONS = ["LEARNER", "ADMIN","PROGRAM_LEAD"]

# No endpoint currently returns the list of valid groups/projects, so these
# are placeholder options — swap in a real fetch once one exists.
GROUP_OPTIONS = ["Unassigned", "Group A", "Group B", "Group C", "Group D"]
PROJECT_OPTIONS = ["Unassigned", "CodeBook", "OpsAgent AI", "Capstone Project"]


def _index_or_zero(options, value):
    return options.index(value) if value in options else 0


def show_users():

    page_header(
        "👥",
        "User Management",
        subtitle="View learners and staff.",
        eyebrow="Admin",
    )

    try:
        with st.spinner("Loading users..."):
            response = requests.get(
                f"{BASE_URL}/users",
                headers={
                    "Authorization": f"Bearer {st.session_state.token}"
                },
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

        is_admin = user["role"] == "admin"

        with st.container(border=True):

            info_col, role_col, group_col, project_col, action_col = st.columns(
                [2.4, 1.6, 1.6, 1.8, 1]
            )

            # -----------------------------
            # User information
            # -----------------------------
            with info_col:
                st.write(f"**{user['email']}**")
                st.markdown(
                    role_badge_html(user["role"]),
                    unsafe_allow_html=True,
                )

            # -----------------------------
            # Role
            # -----------------------------
            with role_col:
                new_role = st.selectbox(
                    "Role",
                    ROLE_OPTIONS,
                    index=_index_or_zero(
                        ROLE_OPTIONS,
                        user["role"],
                    ),
                    key=f"role_{user['id']}",
                    disabled=is_admin,
                )

            # -----------------------------
            # Group
            # -----------------------------
            with group_col:

                if is_admin:
                    st.markdown("**Group**")
                    st.caption("—")
                    new_group = None
                else:
                    new_group = st.selectbox(
                        "Group",
                        GROUP_OPTIONS,
                        index=_index_or_zero(
                            GROUP_OPTIONS,
                            user.get("group"),
                        ),
                        key=f"group_{user['id']}",
                    )

            # -----------------------------
            # Project
            # -----------------------------
            with project_col:

                if is_admin:
                    st.markdown("**Project**")
                    st.caption("—")
                    new_project = None
                else:
                    new_project = st.selectbox(
                        "Project",
                        PROJECT_OPTIONS,
                        index=_index_or_zero(
                            PROJECT_OPTIONS,
                            user.get("project"),
                        ),
                        key=f"project_{user['id']}",
                    )

            # -----------------------------
            # Update button
            # -----------------------------
            with action_col:

                st.write("")

                if is_admin:
                    st.button(
                        "Update",
                        key=f"btn_{user['id']}",
                        disabled=True,
                        use_container_width=True,
                    )

                else:

                    unchanged = (
                        new_role == user["role"]
                        and new_group == user.get("group", "Unassigned")
                        and new_project == user.get("project", "Unassigned")
                    )

                    if st.button(
                        "Update",
                        key=f"btn_{user['id']}",
                        disabled=unchanged,
                        use_container_width=True,
                    ):

                        payload = {
                            "role": new_role,
                            "group": new_group,
                            "project": new_project,
                        }

                        try:
                            with st.spinner("Updating user..."):

                                patch_response = requests.patch(
                                    f"{BASE_URL}/users/{user['id']}/role",
                                    json=payload,
                                    headers={
                                        "Authorization": f"Bearer {st.session_state.token}"
                                    },
                                )

                            if patch_response.status_code == 200:
                                st.success(f"Updated {user['email']}.")
                                st.rerun()

                            else:
                                st.error(
                                    "Couldn't update this user. Please try again."
                                )

                        except requests.RequestException as e:
                            st.error(f"Couldn't reach the backend: {e}")
