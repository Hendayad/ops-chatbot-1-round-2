"""One-off diagnostic: surface the real exception behind the FAILED at-risk nudge.

app.scheduler.runner.run_notification swallows every exception from
delivery with a bare `except Exception`, so the at-risk job's FAILED
status for learner_id=1's nudge (confirmed via check_nudge_status.py)
gives no clue what actually broke. This calls LearnerChatChannel.send()
directly -- one attempt, no tenacity retry wrapper, no swallowing -- and
prints the full traceback.

Usage:
    uv run python debug_nudge_failure.py
"""

from __future__ import annotations

import asyncio
import sys
import traceback

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.atrisk.detector import detect_at_risk  # noqa: E402
from app.atrisk.nudges import build_nudge  # noqa: E402
from app.atrisk.progress_store import get_learner_progress  # noqa: E402
from app.notifications.learner_chat_channel import LearnerChatChannel  # noqa: E402


def main() -> None:
    learner_id = "1"
    progress = get_learner_progress(learner_id)
    if progress is None:
        print(f"No persisted progress snapshot for learner_id={learner_id!r}. Run demo_progress_provider.py first.")
        sys.exit(1)

    result = detect_at_risk(progress)
    print(f"at_risk={result.signals.at_risk} score={result.signals.score}")

    notification = build_nudge(result)
    print(f"Built notification: dedup_key={notification.dedup_key} recipient_id={notification.recipient_id}")

    channel = LearnerChatChannel()
    print("\n--- Calling LearnerChatChannel.send() directly (single attempt, no retry) ---")
    try:
        channel.send(notification)
    except Exception:
        print("\n*** send() raised -- this is the real exception run_notification was swallowing: ***\n")
        traceback.print_exc()
        sys.exit(1)
    else:
        print("send() succeeded with no exception.")


if __name__ == "__main__":
    main()
