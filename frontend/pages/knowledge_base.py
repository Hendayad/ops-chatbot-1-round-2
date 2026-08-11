import json

import streamlit as st
import pandas as pd

from components.styles import page_header
from api.kb import (
    get_materials,
    retire_material,
    get_cohorts,
    onboard_cohort,
    reingest_materials,
    get_material,
)


def show_knowledge_base():

    page_header(
        "📚",
        "Knowledge Base",
        subtitle="Manage the knowledge sources used by the AI assistant.",
        eyebrow="Knowledge Base",
    )

    try:
        # ==========================================================
        # Cohort Loader
        # ==========================================================
        st.subheader("Load a Cohort")
        st.caption(
            "Select a configured cohort and load its approved materials into the knowledge base."
        )

        cohorts_response = get_cohorts(st.session_state.token)
        cohorts = cohorts_response.get("cohorts", [])

        if cohorts:

            cohort_ids = [c["cohort_id"] for c in cohorts]

            col1, col2 = st.columns([4, 1])

            with col1:
                selected_cohort = st.selectbox(
                    "Configured Cohorts",
                    cohort_ids,
                )

            with col2:
                st.write("")
                st.write("")

                if st.button(
                    "Load",
                    use_container_width=True,
                ):
                    with st.spinner("Loading cohort materials..."):
                        stats = onboard_cohort(
                            st.session_state.token,
                            selected_cohort,
                        )

                    st.success(
                        f"Successfully loaded '{selected_cohort}'."
                    )

                    if isinstance(stats, dict):
                        st.info(
                            f"""
Sources Seen: **{stats.get('sources_seen', 0)}**

Sources Ingested: **{stats.get('sources_ingested', 0)}**

Sources Skipped: **{stats.get('sources_skipped', 0)}**

Chunks Written: **{stats.get('chunks_written', 0)}**
"""
                        )

                    st.rerun()

        else:
            st.warning("No cohorts are configured.")

        st.divider()

        # ==========================================================
        # Re-ingest Materials (manual)
        # ==========================================================
        st.subheader("Re-ingest Materials")
        st.caption(
            "Paste a JSON list of approved materials to re-ingest them directly, "
            "outside of a cohort's configured materials folder."
        )

        materials_json = st.text_area(
            "Materials (JSON list)",
            height=150,
            placeholder='[{"source_id": "...", "content": "...", ...}]',
        )

        if st.button("Re-ingest"):
            try:
                parsed_materials = json.loads(materials_json) if materials_json.strip() else []
            except json.JSONDecodeError as e:
                st.error(f"Invalid JSON: {e}")
                parsed_materials = None

            if parsed_materials is not None:
                if not parsed_materials:
                    st.warning("Enter at least one material to ingest.")
                else:
                    with st.spinner("Re-ingesting materials..."):
                        stats = reingest_materials(
                            st.session_state.token,
                            parsed_materials,
                        )

                    st.success("Re-ingestion complete.")

                    if isinstance(stats, dict):
                        st.info(
                            f"""
Sources Seen: **{stats.get('sources_seen', 0)}**

Sources Ingested: **{stats.get('sources_ingested', 0)}**

Sources Skipped: **{stats.get('sources_skipped', 0)}**

Chunks Written: **{stats.get('chunks_written', 0)}**
"""
                        )

                    st.rerun()

        st.divider()

        # ==========================================================
        # Materials
        # ==========================================================
        st.subheader("Knowledge Base Materials")

        with st.spinner("Loading materials..."):
            data = get_materials(st.session_state.token)

        materials = data.get("materials", [])

        if not materials:
            st.info(
                "No materials have been ingested yet.\n\n"
                "Load one of the configured cohorts above."
            )
            return

        df = pd.DataFrame(materials)

        if "content_hash" in df.columns:
            df = df.drop(columns=["content_hash"])

        if "source_id" in df.columns:
            df = df.rename(columns={"source_id": "material_id"})

        if "updated_at" in df.columns:
            df["updated_at"] = pd.to_datetime(
                df["updated_at"]
            ).dt.strftime("%Y-%m-%d %H:%M")

        # material_id is "{cohort}::{source}" (see RawMaterial.source_id), so
        # the cohort a material belongs to can be read straight out of it --
        # no separate backend field or API call needed for the filter below.
        df["cohort"] = df["material_id"].str.split("::").str[0]

        cohort_options = ["All cohorts"] + sorted(df["cohort"].dropna().unique().tolist())
        selected_cohort_filter = st.selectbox(
            "Filter by Cohort",
            cohort_options,
            key="kb_materials_cohort_filter",
        )

        if selected_cohort_filter != "All cohorts":
            df = df[df["cohort"] == selected_cohort_filter]

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
        )

        material_ids = df["material_id"].tolist()

        if not material_ids:
            st.info("No materials for this cohort.")
            return

        st.divider()

        # ==========================================================
        # View Material Content
        # ==========================================================
        st.subheader("View Material Content")

        view_material_id = st.selectbox(
            "Material",
            material_ids,
            key="view_material_select",
        )

        if st.button("View Content"):
            with st.spinner("Loading content..."):
                material_detail = get_material(st.session_state.token, view_material_id)

            st.markdown(f"**Source:** `{material_detail.get('source_id', view_material_id)}`")
            if material_detail.get("updated_at"):
                st.caption(f"Last updated: {material_detail['updated_at']}")

            st.text_area(
                "Content",
                value=material_detail.get("content", "(no content field returned)"),
                height=400,
                disabled=True,
            )

        st.divider()

        # ==========================================================
        # Retire Material
        # ==========================================================
        st.subheader("Retire Material")
        st.caption(
            "Retired materials will no longer be used when answering learners."
        )

        col1, col2 = st.columns([4, 1])

        with col1:
            selected_material = st.selectbox(
                "Material",
                material_ids,
                key="retire_material_select",
            )

        with col2:
            st.write("")
            st.write("")

            if st.button(
                "Retire",
                use_container_width=True,
                type="primary",
            ):
                with st.spinner("Retiring material..."):
                    retire_material(
                        st.session_state.token,
                        selected_material,
                    )

                st.success(
                    f"Material '{selected_material}' retired successfully."
                )

                st.rerun()

    except Exception as e:
        st.error(f"Couldn't load the knowledge base: {e}")