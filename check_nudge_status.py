"""One-off diagnostic: why did the last at-risk job run report nudges_sent=0?

run_scheduled_at_risk_job() flagged learner_id=1 (hend.3ayad@gmail.com) as
at-risk but sent 0 nudges. That's either:
  (a) expected -- a SENT at-risk nudge already exists for this learner
      within the last 7 days (the frequency cap in app/atrisk/nudges.py
      working correctly), or
  (b) a real bug -- delivery was attempted and failed (status=FAILED), or
      never attempted at all (no matching record).

This prints every AT_RISK_NUDGE NotificationRecord for learner_id=1, most
recent first, so we can tell which case we're in without guessing.

Usage:
    uv run python check_nudge_status.py

Needed purely for its import side effect.

User.notification_preference is a string-referenced relationship
("NotificationPreference"). SQLAlchemy resolves that relationship only after
NotificationPreference has been imported.

Without this import, mapper configuration fails with:

InvalidRequestError: failed to locate a name ('NotificationPreference')

This script doesn't otherwise import NotificationPreference, so we import it
here intentionally.
"""
from __future__ import annotations
from app.models.notification_preference import NotificationPreference  # noqa: F401
from app.schemas.notification import NotificationType
from app.services.database import database_service
from sqlmodel import select
from app.models.notification import NotificationRecord



def main() -> None:
    learner_id = "1"
    with database_service.get_session_maker() as session:
        records = session.exec(
            select(NotificationRecord)
            .where(
                NotificationRecord.recipient_id == learner_id,
                NotificationRecord.type == NotificationType.AT_RISK_NUDGE,
            )
            .order_by(NotificationRecord.created_at.desc())  # pyright: ignore[reportAttributeAccessIssue]
        ).all()

    if not records:
        print(f"No AT_RISK_NUDGE records found at all for learner_id={learner_id}.")
        print("-> nudges_sent=0 was NOT the frequency cap -- delivery was never attempted.")
        print("   Worth checking app/atrisk/nudges.py's send_at_risk_nudges / _nudge_eligible next.")
        return

    print(f"Found {len(records)} AT_RISK_NUDGE record(s) for learner_id={learner_id}:\n")
    for r in records:
        print(f"  id={r.id} status={r.status} created_at={r.created_at} dedup_key={r.dedup_key}")

    most_recent = records[0]
    if most_recent.status.value == "sent":
        print(
            f"\n-> Most recent is SENT at {most_recent.created_at}. "
            "That's why the last run skipped -- the 7-day frequency cap is working correctly."
        )
    elif most_recent.status.value == "failed":
        print(
            f"\n-> Most recent is FAILED (created_at={most_recent.created_at}). "
            "Delivery was attempted and failed -- this is a real bug, not the frequency cap."
        )
    else:
        print(f"\n-> Most recent status is '{most_recent.status.value}' -- unexpected, worth a closer look.")


if __name__ == "__main__":
    main()
