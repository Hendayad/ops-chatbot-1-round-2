import streamlit as st
from pathlib import Path

from components.styles import page_header


def show_guide():

    # Only admins can access this page
    if st.session_state.get("role", "").upper() != "ADMIN":
        st.error("You are not authorized to view this page.")
        return

    page_header(
        "📘",
        "Administrator Guide",
        subtitle="System administration and operational documentation.",
        eyebrow="Documentation",
    )

    # Repository root
    repo_root = Path(__file__).resolve().parents[2]

    # docs/admin-guide.md
    guide_path = repo_root / "docs" / "admin-guide.md"

    if guide_path.exists():

        with open(guide_path, "r", encoding="utf-8") as f:
            st.markdown(f.read())

    else:

        st.error(
            f"Admin guide not found.\n\nExpected location:\n{guide_path}"
        )