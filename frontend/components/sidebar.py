import streamlit as st

from components.nav_config import PAGE_ICONS, ROLE_PAGES


def show_sidebar(role, notification_count=0, overdue_ticket_count=0):

    st.sidebar.title("🛠 Ops Console")
    st.sidebar.caption("Operations Support Portal")

    role = (role or "").lower()

    pages = ROLE_PAGES.get(role, [])

    display = []

    for page in pages:

        label = f"{PAGE_ICONS.get(page, '')} {page}"

        if page == "Escalations" and overdue_ticket_count:
            label += f" 🔴 {overdue_ticket_count}"

        if page == "Notifications" and notification_count:
            label += f" ({notification_count})"

        display.append(label)

    selected = st.sidebar.radio(
        "",
        display,
        label_visibility="collapsed",
    )

    page = next(
        (p for p in pages if f" {p}" in selected),
        pages[0] if pages else None,
    )

    # -----------------------------
    # User Card
    # -----------------------------

    user = st.session_state.get("user", {})

    username = user.get("username", "User")
    email = user.get("email", "")
    initial = username[0].upper()

    st.sidebar.markdown("---")

    st.sidebar.markdown(
        f"""
<div style="
    border:1px solid #E5E7EB;
    border-radius:14px;
    padding:12px;
    margin-top:6px;
    margin-bottom:10px;
">

<div style="display:flex;align-items:center;">

<div style="
    width:44px;
    height:44px;
    border-radius:50%;
    background:#2563EB;
    color:white;
    font-size:18px;
    font-weight:700;
    display:flex;
    align-items:center;
    justify-content:center;
    margin-right:12px;
">
{initial}
</div>

<div>

<div style="
    font-size:15px;
    font-weight:600;
    color:#111827;
    line-height:1.2;
">
{username}
</div>

<div style="
    font-size:12px;
    color:#6B7280;
    margin-top:2px;
">
{email}
</div>

<div style="
    display:inline-block;
    margin-top:8px;
    padding:3px 10px;
    background:#EFF6FF;
    color:#1D4ED8;
    border-radius:999px;
    font-size:11px;
    font-weight:600;
">
{role.title()}
</div>

</div>

</div>

</div>
""",
        unsafe_allow_html=True,
    )

    if st.sidebar.button(
        "🚪 Logout",
        use_container_width=True,
    ):
        st.session_state.clear()
        st.rerun()

    return page