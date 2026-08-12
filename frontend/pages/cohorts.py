import streamlit as st
from datetime import date, timedelta

from components.styles import page_header
from api.cohorts import (
    CohortAPIError,
    create_cohort,
    delete_cohort,
    get_cohorts,
    update_cohort,
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



def _parse_date(value, fallback=None):
    """Convert API ISO date strings to datetime.date."""
    if isinstance(value, date):
        return value

    if value:
        try:
            return date.fromisoformat(str(value))
        except ValueError:
            pass

    return fallback


def _sync_expired_cohorts(token, cohorts):
    """
    Disable expired cohorts in the backend/database.

    This runs every time the Cohorts page reruns.
    """
    today = date.today()
    changed = False

    for cohort in cohorts:
        if not cohort.get("enabled", True):
            continue

        cohort_end_date = _parse_date(cohort.get("end_date"))

        if cohort_end_date is None or cohort_end_date >= today:
            continue

        update_cohort(
            token,
            cohort["cohort_id"],
            enabled=False,
        )

        cohort["enabled"] = False
        changed = True

    return changed


@st.dialog("Edit Cohort", width="large")
def edit_cohort_dialog(cohort):
    """Edit cohort metadata and persist changes through the backend API."""

    st.subheader(f"Edit · {cohort['name']}")

    current_start = _parse_date(
        cohort.get("start_date"),
        date.today(),
    )
    current_end = _parse_date(
        cohort.get("end_date"),
        current_start + timedelta(days=3),
    )

    name = st.text_input(
        "Cohort Name*",
        value=cohort.get("name") or "",
        key=f"edit_name_{cohort['cohort_id']}",
    )

    description = st.text_area(
        "Description",
        value=cohort.get("description") or "",
        height=120,
        key=f"edit_description_{cohort['cohort_id']}",
    )

    project = st.text_input(
        "Project Name",
        value=cohort.get("project") or "",
        key=f"edit_project_{cohort['cohort_id']}",
    )

    start_date = st.date_input(
        "Start Date",
        value=current_start,
        key=f"edit_start_{cohort['cohort_id']}",
    )

    end_date = st.date_input(
        "End Date",
        value=current_end,
        key=f"edit_end_{cohort['cohort_id']}",
        help=(
            "End Date cannot be before Start Date, and the cohort "
            "period must be at least 3 days."
        ),
    )

    # Validate the edited date range immediately, before Save is allowed.
    date_errors = []

    if end_date < start_date:
        date_errors.append("End Date cannot be before Start Date.")
    elif (end_date - start_date).days < 3:
        date_errors.append("Cohort period must be at least 3 days.")

    for message in date_errors:
        st.error(message)

    dates_valid = not date_errors

    save_col, cancel_col = st.columns(2)

    with save_col:
        if st.button(
            "Save Changes",
            type="primary",
            use_container_width=True,
            key=f"save_edit_{cohort['cohort_id']}",
            disabled=not dates_valid,
        ):
            errors = []

            if not name.strip():
                errors.append("Cohort Name is required.")

            # Keep backend-request validation as defense in depth.
            if end_date < start_date:
                errors.append("End Date cannot be before Start Date.")

            if (end_date - start_date).days < 3:
                errors.append("Cohort period must be at least 3 days.")

            if errors:
                for message in errors:
                    st.error(message)
            else:
                # If an expired cohort is extended to today/future,
                # reactivate it. Historical cohorts remain disabled.
                enabled = end_date >= date.today()

                token = st.session_state.get("token")

                try:
                    update_cohort(
                        token,
                        cohort["cohort_id"],
                        name=name.strip(),
                        description=description.strip() or None,
                        project=project.strip() or None,
                        start_date=start_date.isoformat(),
                        end_date=end_date.isoformat(),
                        enabled=enabled,
                    )
                except CohortAPIError as exc:
                    st.error(f"Couldn't update cohort: {exc}")
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Couldn't update cohort: {exc}")
                else:
                    st.success(f"Cohort '{name}' updated successfully.")
                    st.rerun()

    with cancel_col:
        if st.button(
            "Cancel",
            use_container_width=True,
            key=f"cancel_edit_{cohort['cohort_id']}",
        ):
            st.rerun()


@st.dialog("Create Cohort", width="large")
def create_cohort_dialog():

    st.subheader("New Cohort")

    name = st.text_input("Cohort Name*")

    description = st.text_area(
        "Description",
        height=120,
    )

    project = st.text_input("Project Name")

    start_date = st.date_input(
        "Start Date",
        value=date.today(),
    )

    minimum_end_date = max(
        date.today(),
        start_date + timedelta(days=3),
    )

    end_date = st.date_input(
        "End Date",
        value=minimum_end_date,
        min_value=minimum_end_date,
        help="The cohort period must be at least 3 days.",
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
            if end_date < date.today():
                errors.append("End Date cannot be before the cohort creation date.")

            if end_date < start_date:
                errors.append("End Date cannot be before Start Date.")

            if (end_date - start_date).days < 3:
                errors.append("Cohort period must be at least 3 days.")

            if errors:
                for message in errors:
                    st.error(message)
            else:
                token = st.session_state.get("token")
                try:
                    create_cohort(
                        token,
                        name=name.strip(),
                        description=description.strip() or None,
                        project=project.strip() or None,
                        start_date=start_date,
                        end_date=end_date,
                        enabled=end_date >= date.today(),
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

        # Persist expired status to the database on every page rerun.
        if _sync_expired_cohorts(token, cohorts):
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

            st.divider()

            is_enabled = bool(cohort.get("enabled", True))

            if is_enabled:
                upload_col, edit_col, delete_col = st.columns(3)

                with upload_col:
                    if st.button(
                        "📤 Upload Materials",
                        key=f"upload_{cohort['cohort_id']}",
                        use_container_width=True,
                    ):
                        upload_materials_dialog(cohort)

                with edit_col:
                    if st.button(
                        "✏️ Edit",
                        key=f"edit_{cohort['cohort_id']}",
                        use_container_width=True,
                    ):
                        edit_cohort_dialog(cohort)

                with delete_col:
                    if st.button(
                        "🗑️ Delete",
                        key=f"delete_{cohort['cohort_id']}",
                        use_container_width=True,
                    ):
                        delete_cohort_dialog(cohort)

            else:
                # Disabled cohort: Edit replaces Upload Materials.
                edit_col, delete_col = st.columns(2)

                with edit_col:
                    if st.button(
                        "✏️ Edit",
                        key=f"edit_{cohort['cohort_id']}",
                        use_container_width=True,
                    ):
                        edit_cohort_dialog(cohort)

                with delete_col:
                    if st.button(
                        "🗑️ Delete",
                        key=f"delete_{cohort['cohort_id']}",
                        use_container_width=True,
                    ):
                        delete_cohort_dialog(cohort)