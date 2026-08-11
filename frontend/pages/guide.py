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

    # frontend/docs/admin-guide.md
    #
    # NOTE: this used to resolve to the repo-root docs/ folder (three levels
    # up from this file), which works when running from a full repo checkout.
    # But this service's Railway build Root Directory is set to /frontend,
    # so only the frontend/ subtree is ever present in its build context --
    # the repo-root docs/ folder never exists in this container, no matter
    # what .dockerignore allows through. The guide now lives inside
    # frontend/docs/ instead, so it's actually part of this service's build.
    # Keep this copy in sync with the repo-root docs/admin-guide.md if that
    # one is ever edited (or point everyone at this one as the source of truth).
    frontend_root = Path(__file__).resolve().parents[1]
    guide_path = frontend_root / "docs" / "admin-guide.md"

    if guide_path.exists():

        with open(guide_path, "r", encoding="utf-8") as f:
            st.markdown(f.read())

    else:

        st.error(
            f"Admin guide not found.\n\nExpected location:\n{guide_path}"
        )