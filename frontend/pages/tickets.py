import streamlit as st
import pandas as pd

from st_aggrid import (
    AgGrid,
    GridOptionsBuilder,
    GridUpdateMode,
)

from components.styles import (
    page_header,
    badge,
    status_kind,
)

from api.tickets import (
    get_tickets,
    resolve_ticket,
)


def show_tickets():

    page_header(
        "🎫",
        "Escalation Tickets",
        subtitle="Conversations the assistant flagged for human follow-up.",
        eyebrow="Support",
    )

    try:

        with st.spinner("Loading tickets..."):
            data = get_tickets(st.session_state.token)

        tickets = data["tickets"]

        if not tickets:
            st.success("No escalation tickets right now 🎉")
            return

        df = pd.DataFrame(tickets)

        display = df[
            [
                "ticket_id",
                "reason",
                "status",
                "summary",
                "created_at",
            ]
        ]

        st.write("### Tickets")
        st.caption("Click a row to view its details.")

        gb = GridOptionsBuilder.from_dataframe(display)

        gb.configure_default_column(
            sortable=True,
            filter=True,
            resizable=True,
        )

        gb.configure_selection(
            selection_mode="single",
            use_checkbox=False,
        )

        gb.configure_pagination(
            enabled=True,
            paginationAutoPageSize=True,
        )

        gb.configure_grid_options(
            suppressRowClickSelection=False,
            rowSelection="single",
            animateRows=True,
        )

        grid_response = AgGrid(
            display,
            gridOptions=gb.build(),
            update_mode=GridUpdateMode.SELECTION_CHANGED,
            fit_columns_on_grid_load=True,
            height=350,
            theme="streamlit",
            reload_data=False,
        )

        selected = grid_response["selected_rows"]

        if len(selected) == 0:
            st.info("Select a ticket from the table above.")
            return

        ticket_id = selected[0]["ticket_id"]

        ticket = df[df["ticket_id"] == ticket_id].iloc[0]

        st.write("")

        with st.container(border=True):

            top_col, badge_col = st.columns([3, 2])

            with top_col:
                st.subheader(f"Ticket {ticket['ticket_id']}")

            with badge_col:
                st.markdown(
                    badge(
                        ticket["status"],
                        status_kind(ticket["status"]),
                    ),
                    unsafe_allow_html=True,
                )

            st.write("### Problem")
            st.info(ticket["problem"])

            st.write("### Context")
            st.write(ticket["context"])

            st.write("### Suggested Next Step")
            st.success(ticket["suggested_next_step"])

            st.write("### Summary")
            st.write(ticket["summary"])

            st.write("### User Goal")
            st.write(ticket["user_goal"])

            st.divider()

            if ticket["status"].lower() == "open":

                if st.button(
                    "✅ Resolve Ticket",
                    type="primary",
                    use_container_width=True,
                ):

                    with st.spinner("Resolving ticket..."):

                        resolve_ticket(
                            st.session_state.token,
                            ticket["ticket_id"],
                        )

                    st.success("Ticket resolved successfully.")

                    st.rerun()

            else:

                st.success("This ticket has already been resolved.")

    except Exception as e:

        st.error(f"Couldn't load tickets: {e}")