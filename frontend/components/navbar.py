import streamlit as st

from components.nav_config import ROLE_PAGES, PAGE_ICONS
from components.styles import badge, ROLE_BADGE


def _initial(name: str) -> str:
    name = (name or "?").strip()
    return name[0].upper() if name else "?"


def _do_logout():
    st.session_state.token = None
    st.session_state.role = None
    st.session_state.user = {}
    st.session_state.pop("messages", None)
    st.session_state.pop("history_loaded", None)
    st.rerun()


def render_top_navbar():
    """Renders the top navigation bar and returns the selected page name."""

    role = (st.session_state.get("role") or "").lower()
    pages = ROLE_PAGES.get(role, [])

    if not pages:
        st.warning("Unknown role — contact an administrator.")
        return None

    user = st.session_state.get("user", {}) or {}
    display_name = user.get("username") or user.get("email") or "Account"
    email = user.get("email", "")
    role_label = role.replace("_", " ").title()

    with st.container(border=False, key="oa_topbar"):

        col_brand, col_nav, col_user = st.columns(
            [2, 6, 2], vertical_alignment="center"
        )

        # ---- Brand ----
        with col_brand:
            st.markdown(
                """
                <div class="oa-brand">
                    <div class="oa-brand-mark">OA</div>
                    <div class="oa-brand-title">OpsAgent</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # ---- Navigation ----
        with col_nav:
            options = [f"{PAGE_ICONS.get(p, '•')}  {p}" for p in pages]
            key = f"top_nav_{role}"

            if hasattr(st, "segmented_control"):
                choice = st.segmented_control(
                    "Navigation",
                    options=options,
                    default=options[0],
                    label_visibility="collapsed",
                    key=key,
                )
                choice = choice or options[0]
            else:
                choice = st.radio(
                    "Navigation",
                    options=options,
                    horizontal=True,
                    label_visibility="collapsed",
                    key=key,
                )

        # ---- User menu ----
        with col_user:
            if hasattr(st, "popover"):
                with st.popover(
                    f"{_initial(display_name)}  {display_name}  ⌄",
                    use_container_width=True,
                ):
                    st.markdown(f"**{display_name}**")
                    if email:
                        st.caption(email)
                    st.markdown(
                        badge(role_label, ROLE_BADGE.get(role, "neutral")),
                        unsafe_allow_html=True,
                    )
                    st.divider()
                    if st.button("Log out", key="oa_logout_btn", use_container_width=True):
                        _do_logout()
            else:
                c_info, c_logout = st.columns([2, 1], vertical_alignment="center")
                with c_info:
                    st.markdown(
                        f"""
                        <div class="oa-user-chip">
                            <div class="oa-avatar">{_initial(display_name)}</div>
                            <div>
                                <div class="oa-user-name">{display_name}</div>
                                {badge(role_label, ROLE_BADGE.get(role, "neutral"))}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with c_logout:
                    if st.button("Log out", key="oa_logout_btn", use_container_width=True):
                        _do_logout()

    return pages[options.index(choice)]