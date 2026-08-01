import streamlit as st
import pandas as pd

from components.styles import page_header
from api.kb import (
    get_materials,
    retire_material,
)


def show_knowledge_base():

    page_header(
        "📚", "Knowledge Base",
        subtitle="Materials the AI assistant draws on when answering learners.",
        eyebrow="Content",
    )

    try:
        with st.spinner("Loading materials..."):
            data = get_materials(st.session_state.token)

        materials = data["materials"]

        if not materials:
            st.info("No materials available yet.")
            return

        df = pd.DataFrame(materials)

        with st.container(border=True):
            st.dataframe(df, use_container_width=True, hide_index=True)

        st.write("")
        st.subheader("Retire a Material")
        st.caption("Retired materials are no longer used by the assistant.")

        col1, col2 = st.columns([3, 1])

        with col1:
            selected = st.selectbox(
                "Material to retire",
                df["material_id"],
                label_visibility="collapsed",
            )

        with col2:
            confirm = st.button("Retire", use_container_width=True)

        if confirm:
            with st.spinner("Retiring material..."):
                retire_material(st.session_state.token, selected)
            st.success(f"Material {selected} retired.")
            st.rerun()

    except Exception as e:
        st.error(f"Couldn't load the knowledge base: {e}")