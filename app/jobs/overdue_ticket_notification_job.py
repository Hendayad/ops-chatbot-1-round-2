"""
Background job for overdue escalation-ticket notifications.

Rules:

- Learners are notified immediately when their issue is escalated.
- Admins are notified only when an escalation remains unresolved
  for more than 2 days.
- Program leads are notified only when an escalation remains
  unresolved for more than 2 days.
- Resolved/closed tickets are ignored.
- Duplicate notifications are not created.
- This job uses the existing UserNotification table.
- No database changes are required.
"""

from app.notifications.escalation_notifications import (
    notify_staff_of_overdue_tickets,
)
from app.services.database import database_service


def run() -> int:
    """
    Find unresolved escalation tickets older than two days and
    create notifications for admins and program leads.

    Returns the number of notifications created.
    """

    with database_service.get_session_maker() as session:

        created_count = notify_staff_of_overdue_tickets(
            session
        )

        return created_count

