"""One-off demo script: prove the real DB-backed ProgressProvider pipeline end-to-end.

Unlike demo_learner_chat_nudge.py (which builds LearnerProgress snapshots
in-memory and hands them to run_at_risk_job directly), this exercises the
actual persistence layer added in app/atrisk/progress_store.py -- the real
write path (upsert_learner_progress) and the real read path
(list_all_learner_progress, which is what app.jobs.atrisk_job.
run_scheduled_at_risk_job -- the function the scheduler actually calls --
uses as its progress_provider).

What it does:
  1. Looks up your own real user account by email (so the nudge, if one
     fires, lands in a chat session you can actually go look at).
  2. Builds a LearnerProgress snapshot deliberately over the default risk
     thresholds (missed_deadlines=3, low progress ratio, inactive 10 days)
     and persists it via upsert_learner_progress -- the real write path.
  3. Calls run_scheduled_at_risk_job() -- the exact zero-arg function
     app/scheduler/scheduler.py has registered -- so this proves the
     scheduler's actual entrypoint works, not a hand-rolled substitute.
  4. Prints the job result summary.

Safe to re-run: upsert_learner_progress overwrites your row each time
(idempotent by learner_id), and the at-risk job itself is idempotent per
UTC day. The nudge is frequency-capped like any real at-risk nudge (7
days by default) -- re-running within that window will skip re-sending,
which is correct, not a bug.

Usage:
    uv run python demo_progress_provider.py your.email@example.com
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime, timedelta

if sys.platform == "win32":
    # See demo_learner_chat_nudge.py's module docstring for why this is
    # needed before any asyncio.run()-driven LangGraph checkpointer call
    # on Windows.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlmodel import select  # noqa: E402

from app.atrisk.progress_store import list_all_learner_progress, upsert_learner_progress  # noqa: E402
from app.jobs.atrisk_job import run_scheduled_at_risk_job  # noqa: E402
from app.models.user import User  # noqa: E402
from app.schemas.progress import LearnerProgress  # noqa: E402
from app.services.database import database_service  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: uv run python demo_progress_provider.py your.email@example.com")
        sys.exit(1)

    email = sys.argv[1]

    with database_service.get_session_maker() as session:
        user = session.exec(select(User).where(User.email == email)).first()
        if user is None:
            print(f"No user found with email {email!r}. Register/log in with this email first.")
            sys.exit(1)
        learner_id = str(user.id)

    print(f"Using learner_id={learner_id!r} (user id for {email})")

    progress = LearnerProgress(
        learner_id=learner_id,
        cohort_id="cohort_demo",
        total_tasks=10,
        completed_tasks=2,  # progress_ratio = 0.2, well under the 0.5 threshold
        missed_deadlines=3,  # over the default threshold of 2
        last_active_at=datetime.now(UTC) - timedelta(days=10),  # over the 7-day inactivity threshold
    )

    print("\n--- Persisting progress snapshot (real write path) ---")
    record = upsert_learner_progress(progress)
    print(f"Upserted LearnerProgressRecord id={record.id}")

    print("\n--- Reading it back (real ProgressProvider read path) ---")
    all_progress = list_all_learner_progress()
    print(f"list_all_learner_progress() returned {len(all_progress)} snapshot(s)")

    print("\n--- Running the real scheduler entrypoint: run_scheduled_at_risk_job() ---")
    result = run_scheduled_at_risk_job()
    print(f"run_date={result.run_date}")
    print(f"evaluated_count={result.evaluated_count}")
    print(f"at_risk_count={result.at_risk_count}")
    print(f"nudges_sent={result.nudges_sent}")
    for detection in result.detections:
        print(
            f"  learner_id={detection.learner_id} at_risk={detection.signals.at_risk} "
            f"score={detection.signals.score} "
            f"(missed_deadlines={detection.signals.missed_deadlines}, "
            f"inactive={detection.signals.inactive}, "
            f"low_progress={detection.signals.low_progress}, "
            f"low_feedback={detection.signals.low_feedback})"
        )

    if result.nudges_sent:
        print("\nA nudge was sent -- reload the Chat Viewer / your chat session to see it appended.")
    elif result.at_risk_count:
        print(
            "\nFlagged at-risk but no nudge sent -- likely frequency-capped "
            "(already nudged within the last 7 days). Check app/atrisk/nudges.py."
        )


if __name__ == "__main__":
    main()
