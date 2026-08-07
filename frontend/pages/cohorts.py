import streamlit as st
from datetime import date

from components.styles import page_header
from api.cohorts import (
    CohortAPIError,
    create_cohort,
    delete_cohort,
    get_cohorts,
    upload_material,
)

# Matches app.kb.schema.SourceType exactly.
MATERIAL_TYPES = {
    "FAQ": "faq",
    "Onboarding": "onboarding",
    "Schedule": "schedule",
    "Program Doc": "program_doc",
}


# =====================================================
# Helpers
# =====================================================

def get_projects(cohorts):
    projects = sorted({c["project"] for c in cohorts if c.get("project")})
    return ["All", *projects]


@st.dialog("Create Cohort", width="large")
def create_cohort_dialog():

    st.subheader("New Cohort")

    name = st.text_input("Cohort Name*")

    description = st.text_area(
        "Description",
        height=120,
    )

    project = st.text_input("Project Name")

    materials_root = st.text_input(
        "Materials Folder (optional)",
        placeholder="materials/my-cohort — auto-generated if left blank",
    )

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
            errors = []
            if not name.strip():
                errors.append("Cohort Name is required.")
            if end_date < start_date:
                errors.append("End Date can't be before Start Date.")

            if errors:
                for message in errors:
                    st.error(message)
            else:
                token = st.session_state.get("token")
                try:
                    create_cohort(
                        token,
                        name=name.strip(),
                        materials_root=materials_root.strip() or None,
                        description=description.strip() or None,
                        project=project.strip() or None,
                        start_date=start_date,
                        end_date=end_date,
                        enabled=True,
                    )
                except CohortAPIError as exc:
                    st.error(f"Couldn't create cohort: {exc}")
                except Exception as exc:  # noqa: BLE001 - surface unexpected errors too
                    st.error(f"Couldn't create cohort: {exc}")
                else:
                    st.success(f"Cohort '{name}' created.")
                    st.rerun()

    with col2:
        if st.button(
            "Cancel",
            use_container_width=True,
        ):
            st.rerun()


@st.dialog("Upload Materials", width="large")
def upload_materials_dialog(cohort):

    st.subheader(f"Upload material · {cohort['name']}")

    title = st.text_input("Material Title*")

    material_type_label = st.selectbox(
        "Material Type*",
        list(MATERIAL_TYPES.keys()),
    )
    material_type = MATERIAL_TYPES[material_type_label]

    uploaded_file = st.file_uploader(
        "Choose File*",
        type=["txt", "md", "markdown", "json"],
        accept_multiple_files=False,
        help=(
            "Accepted file types:\n"
            "• .txt\n"
            "• .md\n"
            "• .markdown\n"
            "• .json\n\n"
            "Maximum file size: 25 MB"
        ),
    )

    st.info(
        """
### Accepted File Types

- 📄 .txt
- 📝 .md
- 📝 .markdown
- 📋 .json

**Maximum upload size:** 25 MB
""",
        icon="ℹ️",
    )

    if uploaded_file:
        st.success(
            f"""
    **Selected File**

    **Name:** {uploaded_file.name}
    """,
            icon="📄",
        )

    col1, col2 = st.columns(2)

    with col1:

        if st.button(
            "Upload",
            use_container_width=True,
        ):

            errors = []

            if not title.strip():
                errors.append("Material Title is required.")

            if uploaded_file is None:
                errors.append("Please choose a file to upload.")

            if uploaded_file is not None:

                from pathlib import Path

                allowed_extensions = {
                    ".txt",
                    ".md",
                    ".markdown",
                    ".json",
                }

                extension = Path(uploaded_file.name).suffix.lower()

                if extension not in allowed_extensions:
                    errors.append(
                        f"Unsupported file type '{extension}'. "
                        "Only .txt, .md, .markdown and .json files are allowed."
                    )

                MAX_SIZE = 25 * 1024 * 1024

                if uploaded_file.size > MAX_SIZE:
                    errors.append(
                        "File exceeds the 25 MB upload limit."
                    )

            if errors:

                for message in errors:
                    st.error(message)

            else:

                token = st.session_state.get("token")

                try:

                    upload_material(
                        token,
                        cohort["cohort_id"],
                        title=title.strip(),
                        material_type=material_type,
                        file_name=uploaded_file.name,
                        file_bytes=uploaded_file.getvalue(),
                    )

                except CohortAPIError as exc:
                    st.error(f"Couldn't upload material: {exc}")

                except Exception as exc:
                    st.error(f"Couldn't upload material: {exc}")

                else:
                    st.success(
                        f"'{title}' uploaded successfully to '{cohort['name']}'."
                    )
                    st.rerun()

    with col2:

        if st.button(
            "Cancel",
            use_container_width=True,
            key="cancel_upload",
        ):
            st.rerun()


@st.dialog("Delete Cohort", width="small")
def delete_cohort_dialog(cohort):

    st.error(
        f"Are you sure you want to delete **{cohort['name']}**?\n\n"
        "This will permanently delete the cohort and all uploaded materials."
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "Delete",
            type="primary",
            use_container_width=True,
        ):
            token = st.session_state.get("token")

            try:
                delete_cohort(
                    token,
                    cohort["cohort_id"],
                    delete_files=True,
                )

            except CohortAPIError as exc:
                st.error(f"Couldn't delete cohort: {exc}")

            except Exception as exc:
                st.error(f"Couldn't delete cohort: {exc}")

            else:
                st.success(f"{cohort['name']} deleted successfully.")
                st.rerun()

    with col2:
        if st.button(
            "Cancel",
            use_container_width=True,
            key="cancel_delete",
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
        cohorts = get_cohorts(token, include_disabled=True)
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

    if project_filter != "All":
        cohorts = [c for c in cohorts if c.get("project") == project_filter]

    if not cohorts:
        st.info("No cohorts found.")
        return

    # =====================================================
    # Cohort Cards
    # =====================================================

    for cohort in cohorts:

        with st.container(border=True):

            title_col, status_col = st.columns([4, 1])
            with title_col:
                st.subheader(cohort["name"])
            with status_col:
                if cohort.get("enabled", True):
                    st.success("Enabled", icon="✅")
                else:
                    st.warning("Disabled", icon="⏸️")

            st.caption(f"ID: {cohort['cohort_id']}")

            if cohort.get("description"):
                st.write(cohort["description"])

            meta_bits = []
            if cohort.get("project"):
                meta_bits.append(f"**Project:** {cohort['project']}")
            if cohort.get("start_date") or cohort.get("end_date"):
                meta_bits.append(
                    f"**Dates:** {cohort.get('start_date') or '?'} → "
                    f"{cohort.get('end_date') or '?'}"
                )
            meta_bits.append(f"**Materials:** {len(cohort.get('materials') or [])}")
            if meta_bits:
                st.markdown(" &nbsp;·&nbsp; ".join(meta_bits))

            st.markdown(
                f"""
**Materials Folder**

`{cohort['materials_root']}`
"""
            )

            st.divider()

            col1, col2= st.columns(2)


            with col1:

                if st.button(
                    "📤 Upload Materials",
                    key=f"upload_{cohort['cohort_id']}",
                    use_container_width=True,
                ):
                    upload_materials_dialog(cohort)

            with col2:

                if st.button(
                    "🗑️ Delete",
                    key=f"delete_{cohort['cohort_id']}",
                    use_container_width=True,
                ):
                    delete_cohort_dialog(cohort)