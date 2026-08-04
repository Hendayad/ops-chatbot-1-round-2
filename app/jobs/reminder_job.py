"""Producer contract.

A future domain producer is responsible for inserting ReminderEvent rows
with the following fields:

- recipient_id: learner receiving the reminder
- type: NotificationType.SESSION_REMINDER or DEADLINE_REMINDER
- due_at: UTC datetime of the scheduled event
- title: human-readable event title

Once persisted, the scheduler discovers these events automatically.
"""

# TODO:
# Wire ReminderEvent creation into the future learning-session/deadline
# domain once that feature exists. This module intentionally does not
# create ReminderEvent records itself.
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.reminders.job import dispatch_due_reminders, get_deliver_fn
from app.services.database import database_service


def run() -> None:
    """Execute one reminder scheduling cycle."""

    with database_service.get_session_maker() as session:
        lead_hours = settings.REMINDER_LEAD_TIME_HOURS

        dispatch_due_reminders(
            session=session,
            now=datetime.now(timezone.utc),
            lead_time=timedelta(hours=lead_hours),
            lead_time_label=f"{lead_hours}h_before",
            deliver_fn=get_deliver_fn("email"),
        )