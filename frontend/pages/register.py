import re

import streamlit as st

from api.register import (
    CohortLoadError,
    RegistrationError,
    get_available_cohorts,
    register,
)
from components.styles import page_header


UNASSIGNED_COHORT_ID = "unassigned"


@st.cache_data(ttl=60)
def _load_cohorts() -> list[dict[str, str]]:
    """Load active cohorts with a short cache to avoid repeated API calls."""
    return get_available_cohorts()


def show_register() -> None:
    page_header(
        "📝",
        "Create Account",
        subtitle="Set up access to the Operations Support Portal.",
    )

    try:
        cohorts = _load_cohorts()
    except CohortLoadError as exc:
        st.error(
            "Available cohorts could not be loaded from the backend. "
            "This is a loading error, not the same as having no enabled cohorts."
        )
        st.caption(str(exc))

        if st.button("Retry loading cohorts", use_container_width=True):
            _load_cohorts.clear()
            st.rerun()

        return

    with st.form("register_form", border=True):
        first_col, last_col = st.columns(2)

        with first_col:
            first_name = st.text_input("First Name")

        with last_col:
            last_name = st.text_input("Last Name")

        username = st.text_input("Username")
        email = st.text_input("Email")

        if cohorts:
            cohort_ids_by_name = {
                cohort["name"]: cohort["cohort_id"]
                for cohort in cohorts
            }

            selected_cohort_name = st.selectbox(
                "Cohort",
                options=["Select your cohort"] + list(cohort_ids_by_name),
            )

            selected_cohort_id = cohort_ids_by_name.get(
                selected_cohort_name
            )

        else:
            selected_cohort_id = UNASSIGNED_COHORT_ID
            st.selectbox(
                "Cohort",
                options=["No active cohort available"],
                disabled=True,
            )
            st.info(
                "There are no active cohorts right now. "
                "Your account will be created as 'unassigned' and an "
                "administrator can assign you later."
            )

        password = st.text_input("Password", type="password")
        confirm_password = st.text_input(
            "Confirm Password",
            type="password",
        )

        submitted = st.form_submit_button(
            "Register",
            use_container_width=True,
        )

    if not submitted:
        return

    if not first_name.strip():
        st.warning("First name is required.")

    elif not last_name.strip():
        st.warning("Last name is required.")

    elif not username.strip():
        st.warning("Username is required.")

    elif not email.strip():
        st.warning("Email is required.")

    elif "@" not in email:
        st.warning("Enter a valid email address.")

    elif not selected_cohort_id:
        st.warning("Please select your cohort.")

    elif not password:
        st.warning("Password is required.")

    elif len(password) < 8:
        st.warning("Password must be at least 8 characters.")

    elif not re.search(r"[A-Z]", password):
        st.warning(
            "Password must contain at least one uppercase letter."
        )

    elif not re.search(r"[a-z]", password):
        st.warning(
            "Password must contain at least one lowercase letter."
        )

    elif not re.search(r"\d", password):
        st.warning("Password must contain at least one number.")

    elif not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        st.warning(
            "Password must contain a special character, "
            "such as !, @, #, $, %, or &."
        )

    elif password != confirm_password:
        st.error("Passwords do not match.")

    else:
        try:
            with st.spinner("Creating account..."):
                register(
                    email=email,
                    username=username,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    cohort_id=selected_cohort_id,
                )

            st.success(
                "Account created successfully! Please login."
            )

        except RegistrationError as exc:
            st.error(f"Registration failed: {exc}")