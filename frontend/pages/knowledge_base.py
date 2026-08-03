import streamlit as st
import pandas as pd

from components.styles import page_header
from api.kb import (
    get_materials,
    retire_material,
    get_cohorts,
    onboard_cohort,
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

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
        )

        st.divider()

        # ==========================================================
        # Retire Material
        # ==========================================================
        st.subheader("Retire Material")
        st.caption(
            "Retired materials will no longer be used when answering learners."
        )

        material_ids = df["material_id"].tolist()

        col1, col2 = st.columns([4, 1])

        with col1:
            selected_material = st.selectbox(
                "Material",
                material_ids,
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