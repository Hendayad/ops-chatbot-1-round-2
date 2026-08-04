import streamlit as st
import requests

from components.styles import page_header, role_badge_html
from api.config import BASE_URL

ROLE_OPTIONS = ["LEARNER", "ADMIN", "PROGRAM_LEAD"]
COHORT_OPTIONS = ["Unassigned", "Group A", "Group B", "Group C", "Group D"]


def _index_or_zero(options, value):
    return options.index(value) if value in options else 0


def show_users():

    page_header(
        "👥",
        "User Management",
        subtitle="View learners and staff.",
        eyebrow="Program Lead",
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

        is_program_lead = user["role"] == "program_lead"

        with st.container(border=True):

            info_col, role_col, cohort_col, action_col = st.columns(
                [2.8, 1.8, 1.8, 1]
            )

            with info_col:
                st.write(f"**{user['email']}**")
                st.markdown(
                    role_badge_html(user["role"]),
                    unsafe_allow_html=True,
                )

            with role_col:
                new_role = st.selectbox(
                    "Role",
                    ROLE_OPTIONS,
                    index=_index_or_zero(
                        ROLE_OPTIONS,
                        user["role"].upper(),
                    ),
                    key=f"role_{user['id']}",
                    disabled=is_program_lead,
                )

            is_learner_selected = (not is_program_lead) and new_role == "LEARNER"

            with cohort_col:
                if is_learner_selected:
                    new_cohort = st.selectbox(
                        "Cohort",
                        COHORT_OPTIONS,
                        index=_index_or_zero(
                            COHORT_OPTIONS,
                            user.get("cohort"),
                        ),
                        key=f"cohort_{user['id']}",
                    )
                else:
                    st.markdown("**Cohort**")
                    st.caption("—")
                    new_cohort = None

            with action_col:

                st.write("")

                if is_program_lead:
                    st.button(
                        "Update",
                        key=f"btn_{user['id']}",
                        disabled=True,
                        use_container_width=True,
                    )

                else:

                    current_cohort = user.get("cohort") or "Unassigned"

                    unchanged = (
                        new_role.lower() == user["role"]
                        and (new_cohort or "Unassigned") == current_cohort
                    )

                    if st.button(
                        "Update",
                        key=f"btn_{user['id']}",
                        disabled=unchanged,
                        use_container_width=True,
                    ):

                        payload = {
                            "role": new_role.lower(),
                            "cohort": new_cohort if is_learner_selected else None,
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
                                st.error("Couldn't update this user. Please try again.")

                        except requests.RequestException as e:
                            st.error(f"Couldn't reach the backend: {e}")