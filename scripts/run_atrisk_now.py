"""Manually trigger the at-risk job on demand (rather than waiting for the 24h scheduler interval) and report exactly where any nudge landed.

Safe to run repeatedly -- the job is idempotent by design (see
app/jobs/atrisk_job.py's module docstring): re-running for the same UTC
day upserts state instead of duplicating it, and nudge delivery is
deduplicated by dedup_key.

Local-only ops utility -- do not run against a deployed environment without confirming the target DB first.
"""

from sqlalchemy import text

from app.jobs.atrisk_job import run_scheduled_at_risk_job
from app.services.database import database_service

print("Triggering at-risk job...")
result = run_scheduled_at_risk_job()
print(f"  run_date={result.run_date}")
print(f"  evaluated_count={result.evaluated_count}")
print(f"  at_risk_count={result.at_risk_count}")
print(f"  nudges_sent={result.nudges_sent}")

print("\nCurrent notificationrecord rows for AT_RISK_NUDGE:")
with database_service.engine.connect() as conn:
    rows = conn.execute(
        text(
            """
            SELECT recipient_id, status, dedup_key, created_at
            FROM notificationrecord
            WHERE type = 'AT_RISK_NUDGE'
            ORDER BY created_at DESC
            LIMIT 5
            """
        )
    ).fetchall()
    for r in rows:
        print(f"  recipient_id={r.recipient_id} status={r.status} dedup_key={r.dedup_key} created_at={r.created_at}")

    print("\nSession(s) belonging to that recipient (check these in /chat-viewer):")
    if rows:
        recipient_id = rows[0].recipient_id
        sessions = conn.execute(
            text('SELECT id, name FROM session WHERE user_id = :uid ORDER BY created_at DESC LIMIT 5'),
            {"uid": int(recipient_id)},
        ).fetchall()
        for s in sessions:
            print(f"  session_id={s.id} name={s.name!r}")
    else:
        print("  (no AT_RISK_NUDGE records exist yet)")
