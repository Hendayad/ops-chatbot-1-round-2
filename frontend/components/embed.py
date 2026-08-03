import os
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

ASSETS_DIR = Path(__file__).resolve().parent.parent / "static"

# Same backend the rest of the app talks to (see pages/users.py, settings.py).
# BACKEND_URL (e.g. api/config.py's BASE_URL) already points at the real deployed
# backend and includes a "/api/v1" suffix; this embedded widget builds its own
# "/api/v1/..." paths, so strip that suffix rather than hardcoding localhost,
# which only worked when frontend and backend ran on the same machine.
API_BASE = os.getenv("BACKEND_URL", "http://127.0.0.1:8000/api/v1").removesuffix("/api/v1")


def render_asset(filename: str, height: int, scrolling: bool = True):
    """Load an HTML file from /assets, inject the current session token and
    API base in place of the file's own login form, and embed it as-is."""

    html = (ASSETS_DIR / filename).read_text(encoding="utf-8")

    token = st.session_state.get("token", "") or ""

    html = html.replace("__API_BASE__", API_BASE).replace("__API_TOKEN__", token)

    components.html(html, height=height, scrolling=scrolling)