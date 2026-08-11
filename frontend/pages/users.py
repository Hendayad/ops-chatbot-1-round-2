import requests
import streamlit as st

from api.config import BASE_URL
from api.cohorts import get_cohorts
from components.styles import (
    page_header,
    role_badge_html,
    cohort_badge_html,
)


ROLE_OPTIONS = ["LEARNER", "ADMIN", "PROGRAM_LEAD"]

def _index_or_zero(options, value):
    return options.index(value) if value in options else 0


def _get_user_name(user):
    """
    Build the user's display name from first_name and last_name.
    """
    first_name = (user.get("first_name") or "").strip()
    last_name = (user.get("last_name") or "").strip()

    full_name = f"{first_name} {last_name}".strip()

    if full_name:
        return full_name

    # Fallback if first/last name are missing
    return user.get("username", "Unknown User")


def show_users():

    page_header(
        "👥",
        "User Management",
        subtitle="View learners and staff.",
        eyebrow="Admin",
    )

    # -----------------------------
    # Load users
    # -----------------------------
    try:
        with st.spinner("Loading users..."):
            response = requests.get(
                f"{BASE_URL}/users/",
                headers={
                    "Authorization": f"Bearer {st.session_state.token}"
                },
            )

    except requests.RequestException as e:
        st.error(f"Couldn't reach the backend: {e}")
        return

    if response.status_code != 200:
        st.error(
            f"Couldn't load users. "
            f"Status code: {response.status_code}"
        )
        return

    users = response.json()

    if not users:
        st.info("No users found.")
        return

    # -----------------------------
    # Load cohorts
    # -----------------------------
    try:
        cohorts = get_cohorts(st.session_state.token)

    except requests.RequestException as e:
        st.error(f"Couldn't load cohorts: {e}")
        return

    # -----------------------------
    # Cohort mappings
    # -----------------------------

    # Display name -> ID
    cohort_map = {
        cohort["name"]: cohort["cohort_id"]
        for cohort in cohorts
    }

    # ID -> display name
    cohort_name_map = {
        cohort["cohort_id"]: cohort["name"]
        for cohort in cohorts
    }

    COHORT_OPTIONS = ["Unassigned"] + list(cohort_map.keys())

    # -----------------------------
    # Display users
    # -----------------------------
    for user in users:

        role = user["role"].lower()

        is_staff = role in (
            "admin",
            "program_lead",
        )

        # -----------------------------
        # Get user's name
        # -----------------------------
        user_name = _get_user_name(user)

        # -----------------------------
        # Get current cohort
        # -----------------------------
        current_cohort_name = cohort_name_map.get(
            user.get("cohort_id"),
            "Unassigned",
        )

        with st.container(border=True):

            info_col, role_col, cohort_col, action_col = st.columns(
                [2.8, 1.8, 1.8, 1]
            )

            # -----------------------------
            # User information
            # -----------------------------
            with info_col:

                # Name
                st.markdown(
                    f"**{user_name}**"
                )

                # Email
                st.caption(
                    user.get("email", "No email")
                )

                # Role badge
                st.markdown(
                    role_badge_html(user["role"]),
                    unsafe_allow_html=True,
                )

                # Cohort badge
                if not is_staff:

                    st.markdown(
                        cohort_badge_html(
                            current_cohort_name
                        ),
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
                        user["role"].upper(),
                    ),
                    key=f"role_{user['id']}",
                    disabled=is_staff,
                )

            # -----------------------------
            # Cohort
            # -----------------------------
            with cohort_col:

                if is_staff:

                    st.markdown("**Cohort**")
                    st.caption("—")

                    new_cohort = None

                else:

                    new_cohort = st.selectbox(
                        "Cohort",
                        COHORT_OPTIONS,
                        index=_index_or_zero(
                            COHORT_OPTIONS,
                            current_cohort_name,
                        ),
                        key=f"cohort_{user['id']}",
                    )

            # -----------------------------
            # Update button
            # -----------------------------
            with action_col:

                st.write("")

                if is_staff:

                    st.button(
                        "Update",
                        key=f"btn_{user['id']}",
                        disabled=True,
                        use_container_width=True,
                    )

                else:

                    unchanged = (
                        new_role.lower() == role
                        and new_cohort == current_cohort_name
                    )

                    if st.button(
                        "Update",
                        key=f"btn_{user['id']}",
                        disabled=unchanged,
                        use_container_width=True,
                    ):

                        payload = {
                            "role": new_role.lower(),
                            "cohort": (
                                None
                                if new_cohort == "Unassigned"
                                else cohort_map[new_cohort]
                            ),
                        }

                        try:

                            with st.spinner(
                                "Updating user..."
                            ):

                                patch_response = requests.patch(
                                    f"{BASE_URL}/users/{user['id']}/role",
                                    json=payload,
                                    headers={
                                        "Authorization": (
                                            f"Bearer "
                                            f"{st.session_state.token}"
                                        )
                                    },
                                )

                            if patch_response.status_code == 200:

                                st.success(
                                    f"Updated {user_name}."
                                )

                                st.rerun()

                            else:

                                try:
                                    error = patch_response.json()
                                except Exception:
                                    error = patch_response.text

                                st.error(
                                    f"Update failed: {error}"
                                )

                        except requests.RequestException as e:

                            st.error(
                                f"Couldn't reach the backend: {e}"
                            )

