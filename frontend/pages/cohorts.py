import streamlit as st
import pandas as pd
from datetime import date

from components.styles import page_header


# =====================================================
# Demo Data
# Replace with API later
# =====================================================

DEMO_COHORTS = [
    {
        "id": 1,
        "name": "AI July 2026",
        "description": "Artificial Intelligence Scholarship Cohort",
        "project": "OpsAgent AI",
        "learners": 42,
        "materials": 18,
        "created": "2026-07-01",
    },
    {
        "id": 2,
        "name": "DEPI Round 2",
        "description": "Digital Egypt Pioneers Initiative",
        "project": "CodeBook",
        "learners": 35,
        "materials": 12,
        "created": "2026-06-15",
    },
    {
        "id": 3,
        "name": "Summer Internship",
        "description": "Engineering Summer Internship",
        "project": "Capstone",
        "learners": 27,
        "materials": 9,
        "created": "2026-05-10",
    },
]


# =====================================================
# Helpers
# =====================================================

def get_projects():

    projects = sorted(
        list(
            set(
                cohort["project"]
                for cohort in DEMO_COHORTS
            )
        )
    )

    return ["All"] + projects


def create_cohort_dialog():

    with st.dialog("Create Cohort", width="large"):

        st.subheader("New Cohort")

        name = st.text_input("Cohort Name")

        description = st.text_area(
            "Description",
            height=120,
        )

        project = st.text_input(
            "Project Name",
        )

        start = st.date_input(
            "Start Date",
            value=date.today(),
        )

        end = st.date_input(
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
                    "Cohort created successfully.\n\n(Backend integration coming in Module 10.)"
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
        get_projects(),
    )

    cohorts = DEMO_COHORTS.copy()

    if search:

        cohorts = [
            c
            for c in cohorts
            if search.lower()
            in c["name"].lower()
        ]

    if project_filter != "All":

        cohorts = [
            c
            for c in cohorts
            if c["project"] == project_filter
        ]

    if not cohorts:

        st.info("No cohorts found.")

        return
        # =====================================================
    # Cohort Cards
    # =====================================================

    for cohort in cohorts:

        with st.container(border=True):

            title_col, stats_col = st.columns([4, 2])

            with title_col:

                st.subheader(cohort["name"])

                st.caption(cohort["description"])

                st.markdown(
                    f"""
**Project:** {cohort['project']}

**Created:** {cohort['created']}
"""
                )

            with stats_col:

                st.metric(
                    "Learners",
                    cohort["learners"],
                )

                st.metric(
                    "Materials",
                    cohort["materials"],
                )

            st.divider()

            btn1, btn2, btn3 = st.columns(3)

            with btn1:

                if st.button(
                    "📂 Open",
                    key=f"open_{cohort['id']}",
                    use_container_width=True,
                ):

                    st.session_state.selected_cohort = cohort
                    st.session_state.page = "Cohort Details"

                    st.rerun()

            with btn2:

                if st.button(
                    "📤 Upload Materials",
                    key=f"upload_{cohort['id']}",
                    use_container_width=True,
                ):

                    st.info(
                        f"Upload page for **{cohort['name']}** will be connected to the backend later."
                    )

            with btn3:

                if st.button(
                    "📊 Analytics",
                    key=f"analytics_{cohort['id']}",
                    use_container_width=True,
                ):

                    st.info(
                        f"Analytics page for **{cohort['name']}** coming soon."
                    )