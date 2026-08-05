import streamlit as st
from datetime import date

from components.styles import page_header
from api.cohorts import get_cohorts


# =====================================================
# Helpers
# =====================================================

def get_projects(cohorts):
    # Backend currently doesn't expose projects.
    return ["All"]


@st.dialog("Create Cohort", width="large")
def create_cohort_dialog():

    st.subheader("New Cohort")

    name = st.text_input("Cohort Name")

    description = st.text_area(
        "Description",
        height=120,
    )

    project = st.text_input("Project Name")

    start_date = st.date_input(
        "Start Date",
        value=date.today(),
    )

    end_date = st.date_input(
        "End Date",
        value=date.today(),
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "Create",
            use_container_width=True,
        ):
            st.success(
                "Create Cohort endpoint has not been implemented yet."
            )

    with col2:
        if st.button(
            "Cancel",
            use_container_width=True,
        ):
            st.rerun()


# =====================================================
# Page
# =====================================================

def show_cohorts():

    page_header(
        "📂",
        "Cohorts",
        subtitle="Manage learner cohorts and their materials.",
        eyebrow="Program Lead",
    )

    token = st.session_state.get("token")

    if not token:
        st.error("You are not logged in.")
        return

    try:
        cohorts = get_cohorts(token)
    except Exception as e:
        st.error(f"Couldn't load cohorts: {e}")
        return

    top_left, top_right = st.columns([5, 1])

    with top_left:

        search = st.text_input(
            "Search Cohorts",
            placeholder="Search by name...",
        )

    with top_right:

        st.write("")
        st.write("")

        if st.button(
            "➕ Create",
            use_container_width=True,
        ):
            create_cohort_dialog()

    project_filter = st.selectbox(
        "Project",
        get_projects(cohorts),
    )

    if search:
        cohorts = [
            cohort
            for cohort in cohorts
            if search.lower() in cohort["name"].lower()
        ]

    if not cohorts:
        st.info("No cohorts found.")
        return

    # =====================================================
    # Cohort Cards
    # =====================================================

    for cohort in cohorts:

        with st.container(border=True):

            st.subheader(cohort["name"])

            st.caption(f"ID: {cohort['cohort_id']}")

            st.markdown(
                f"""
**Materials Folder**

`{cohort['materials_root']}`
"""
            )

            st.divider()

            col1, col2 = st.columns(2)

            with col1:

                if st.button(
                    "📂 Open",
                    key=f"open_{cohort['cohort_id']}",
                    use_container_width=True,
                ):
                    st.session_state.selected_cohort = cohort
                    st.session_state.page = "Cohort Details"
                    st.rerun()

            with col2:

                if st.button(
                    "📤 Upload Materials",
                    key=f"upload_{cohort['cohort_id']}",
                    use_container_width=True,
                ):
                    st.info(
                        f"Upload materials for {cohort['name']} (backend integration pending)."
                    )