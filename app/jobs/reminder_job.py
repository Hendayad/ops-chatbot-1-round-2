from datetime import datetime, timedelta, timezone


from app.reminders.job import dispatch_due_reminders, get_deliver_fn
from app.services.database import DatabaseService


from app.core.config import settings


def run() -> None:
    """Execute one reminder scheduling cycle."""
    db = DatabaseService()

    with db.get_session_maker() as session:
        lead_hours = settings.REMINDER_LEAD_TIME_HOURS

        dispatch_due_reminders(
            session=session,
            now=datetime.now(timezone.utc),
            lead_time=timedelta(hours=lead_hours),
            lead_time_label=f"{lead_hours}h_before",
            deliver_fn=get_deliver_fn("email"),
        )