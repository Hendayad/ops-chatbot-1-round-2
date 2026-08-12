import secrets
import string

import requests
import streamlit as st

from api.config import BASE_URL
from api.cohorts import get_cohorts
from api.users import create_user, admin_reset_password
from components.styles import (
    page_header,
    role_badge_html,
    cohort_badge_html,
)


ROLE_OPTIONS = ["LEARNER", "ADMIN", "PROGRAM_LEAD"]
UNASSIGNED_COHORT_ID = "unassigned"
UNASSIGNED_COHORT_LABEL = "Unassigned"


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


def _generate_password(length=12):
    """
    Generate a random, secure password with letters, digits, and symbols.
    """
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def show_users():

    page_header(
        "👥",
        "User Management",
        subtitle="View learners and staff.",
        eyebrow="Program Lead",
    )

    # -----------------------------
    # Add user
    # -----------------------------
    with st.expander("➕ Add a new user"):
        with st.form("add_user_form", clear_on_submit=True):
            col1, col2 = st.columns(2)

            with col1:
                new_first_name = st.text_input("First name")
                new_email = st.text_input("Email")
                new_password = st.text_input("Password", type="password")

            with col2:
                new_last_name = st.text_input("Last name")
                new_username = st.text_input("Username")
                new_role_input = st.selectbox("Role", ROLE_OPTIONS)

            submitted = st.form_submit_button("Create user")

            if submitted:
                if not all([new_first_name, new_last_name, new_email, new_username, new_password]):
                    st.error("Please fill in all fields.")
                elif len(new_password) < 8:
                    st.error("Password must be at least 8 characters long.")
                else:
                    try:
                        create_user(
                            st.session_state.token,
                            email=new_email,
                            username=new_username,
                            first_name=new_first_name,
                            last_name=new_last_name,
                            password=new_password,
                            role=new_role_input.lower(),
                        )
                        st.success(f"Created user {new_first_name} {new_last_name}.")
                        st.rerun()

                    except requests.HTTPError as e:
                        try:
                            detail = e.response.json().get("detail", str(e))
                        except Exception:
                            detail = str(e)
                        st.error(f"Couldn't create user: {detail}")

                    except requests.RequestException as e:
                        st.error(f"Couldn't reach the backend: {e}")

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

    COHORT_OPTIONS = [UNASSIGNED_COHORT_LABEL] + list(cohort_map.keys())

    # -----------------------------
    # Search & filter controls
    # -----------------------------
    search_col, role_col, cohort_col = st.columns([2.4, 1.3, 1.3])

    with search_col:
        search_query = st.text_input(
            "Search",
            placeholder="Search by name, or email...",
            label_visibility="collapsed",
        )

    with role_col:
        role_filter = st.selectbox(
            "Filter by role",
            ["All roles"] + ROLE_OPTIONS,
            label_visibility="collapsed",
        )

    with cohort_col:
        cohort_filter = st.selectbox(
            "Filter by cohort",
            ["All cohorts"] + COHORT_OPTIONS,
            label_visibility="collapsed",
        )

    # -----------------------------
    # Apply filters
    # -----------------------------
    filtered_users = []

    query = search_query.strip().lower()

    for user in users:

        user_name = _get_user_name(user)
        user_role = user["role"].upper()
        user_cohort_name = cohort_name_map.get(
            user.get("cohort_id"),
            UNASSIGNED_COHORT_LABEL,
        )

        # Search match (name, username, email)
        if query:
            haystack = " ".join(
                filter(None, [
                    user_name.lower(),
                    (user.get("username") or "").lower(),
                    (user.get("email") or "").lower(),
                ])
            )
            if query not in haystack:
                continue

        # Role filter
        if role_filter != "All roles" and user_role != role_filter:
            continue

        # Cohort filter
        if cohort_filter != "All cohorts" and user_cohort_name != cohort_filter:
            continue

        filtered_users.append(user)

    st.caption(f"{len(filtered_users)} of {len(users)} users")

    if not filtered_users:
        st.info("No users match your search/filters.")
        return

    # -----------------------------
    # Display users
    # -----------------------------
    for user in filtered_users:

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
            UNASSIGNED_COHORT_LABEL,
        )

        reset_key = f"show_reset_{user['id']}"
        generated_pw_key = f"generated_pw_{user['id']}"

        with st.container(border=True):

            info_col, role_col_ui, cohort_col_ui, action_col = st.columns(
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
            with role_col_ui:

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
            with cohort_col_ui:

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
            # Update / Reset password
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
                                UNASSIGNED_COHORT_ID
                                if new_cohort == UNASSIGNED_COHORT_LABEL
                                else cohort_map[new_cohort]
                            ),
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
                                st.success(f"Updated {user_name}.")
                                st.rerun()
                            else:
                                try:
                                    error = patch_response.json()
                                except Exception:
                                    error = patch_response.text
                                st.error(f"Update failed: {error}")

                        except requests.RequestException as e:
                            st.error(f"Couldn't reach the backend: {e}")

                if st.button(
                    "Reset Password",
                    key=f"reset_btn_{user['id']}",
                    use_container_width=True,
                ):
                    st.session_state[reset_key] = True

            # -----------------------------
            # Generated password panel
            # -----------------------------
            if st.session_state.get(reset_key, False):

                st.divider()
                st.caption(f"Reset password for **{user_name}**")

                gen_col, confirm_col, cancel_col = st.columns([1, 1, 1])

                with gen_col:
                    if st.button(
                        "Generate password",
                        key=f"gen_btn_{user['id']}",
                        use_container_width=True,
                    ):
                        st.session_state[generated_pw_key] = _generate_password()

                if generated_pw_key in st.session_state:

                    st.code(st.session_state[generated_pw_key], language=None)
                    st.caption("Click the copy icon above, then confirm to set it.")

                    with confirm_col:
                        if st.button(
                            "Confirm & set",
                            key=f"confirm_reset_{user['id']}",
                            use_container_width=True,
                        ):
                            try:
                                admin_reset_password(
                                    st.session_state.token,
                                    user["id"],
                                    st.session_state[generated_pw_key],
                                )
                                st.success(
                                    f"Password reset for {user_name}. "
                                    f"Make sure you copied it — it won't be shown again."
                                )
                                st.session_state.pop(generated_pw_key, None)
                                st.session_state[reset_key] = False
                                st.rerun()

                            except requests.HTTPError as e:
                                try:
                                    detail = e.response.json().get("detail", str(e))
                                except Exception:
                                    detail = str(e)
                                st.error(f"Couldn't reset password: {detail}")

                            except requests.RequestException as e:
                                st.error(f"Couldn't reach the backend: {e}")

                with cancel_col:
                    if st.button(
                        "Cancel",
                        key=f"cancel_reset_{user['id']}",
                        use_container_width=True,
                    ):
                        st.session_state[reset_key] = False
                        st.session_state.pop(generated_pw_key, None)
                        st.rerun()