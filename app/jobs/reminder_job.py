from datetime import datetime, timedelta, timezone


from app.reminders.job import dispatch_due_reminders
from app.services.database import DatabaseService


def run() -> None:
    """Execute one reminder scheduling cycle."""
    db = DatabaseService()

    with db.get_session_maker() as session:
        dispatch_due_reminders(
            session=session,
            now=datetime.now(timezone.utc),
            lead_time=timedelta(hours=24),
            lead_time_label="24h_before",
        )