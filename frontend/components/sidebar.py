import streamlit as st

from components.nav_config import PAGE_ICONS, ROLE_PAGES


import streamlit as st

from components.nav_config import PAGE_ICONS, ROLE_PAGES


def show_sidebar(role, notification_count=0, overdue_ticket_count=0):

    st.sidebar.title("🛠 Ops Console")
    st.sidebar.caption("Operations Support Portal")

    role = (role or "").lower()

    pages = ROLE_PAGES.get(role, [])

    display = []

    for page in pages:
        label = f"{PAGE_ICONS.get(page,'')} {page}"

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

    # Safe page detection
    page = next(
        (p for p in pages if f" {p}" in selected),
        pages[0] if pages else None
    )

    st.sidebar.divider()

    user = st.session_state.get("user", {})

    st.sidebar.markdown("### 👤 User")

    st.sidebar.write(user.get("username", "User"))

    if user.get("email"):
        st.sidebar.caption(user["email"])

    st.sidebar.caption(f"Role: {role}")

    st.sidebar.divider()

    if st.sidebar.button("🚪 Logout", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    return page