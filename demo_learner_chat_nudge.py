"""One-off demo script: prove LearnerChatChannel delivers a real nudge.

Proves the nudge is safely appended in-chat for REAL learners (not the
fabricated ids from seed_atrisk_demo_data.py, which don't resolve to a
real chat session -- see app/notifications/learner_chat_channel.py's
module docstring for why).

What it does, step by step, all through the real app code paths (run this
with the db container up and migrations applied, same as
seed_atrisk_demo_data.py -- no HTTP calls, no running uvicorn needed):

  1. Creates (or reuses) two real demo learner accounts.
  2. Creates a real chat Session for each, and seeds a couple of prior turns
     directly into that session's LangGraph checkpoint -- standing in for a
     conversation the learner already had, so this proves the nudge
     APPENDS to real history instead of wiping it (the exact risk flagged
     in LangGraphAgent.append_message's docstring).
  3. Builds a LearnerProgress snapshot for each learner, deliberately over
     the default risk thresholds, with learner_id = str(user.id) -- the
     one identity link LearnerChatChannel's default_session_resolver
     actually supports today.
  4. Runs the real app.jobs.atrisk_job.run_at_risk_job pipeline against
     just these two learners, with sender=LearnerChatChannel() -- the same
     call path a real scheduled run would use. This also persists real
     AtRiskStateRecord rows, so these two learners will show up on the Ops
     dashboard too, alongside (but distinguishable from) the fabricated
     learner_0000.. rows from seed_atrisk_demo_data.py.
  5. Reads back each learner's full chat history and prints it, so you can
     see: [seeded prior turns] + [the nudge], in order, nothing lost.

Safe to re-run for setup (reuses the same accounts/sessions by email), but
note the nudge itself is frequency-capped like any real at-risk nudge
(NUDGE_FREQUENCY_DAYS_DEFAULT in app/atrisk/nudges.py, 7 days): re-running
within the same window will just skip re-sending rather than appending a
second nudge -- the chat history readback still runs either way.

Usage:
    uv run python demo_learner_chat_nudge.py
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import UTC, datetime, timedelta

if sys.platform == "win32":
    # psycopg's async mode (used by LangGraph's AsyncPostgresSaver checkpointer)
    # can't run on Windows' default ProactorEventLoop -- asyncio.run() picks
    # that by default on Windows, which is what made the connection pool hang
    # and time out here. Switching to the selector-based policy before any
    # asyncio.run() call fixes it. uvicorn apparently isn't hitting this today
    # only because nothing has driven the LangGraph checkpointer through a
    # plain `uv run python ...` entrypoint before -- worth checking whether
    # app/main.py needs the same fix before the real /chat endpoint is relied
    # on for a live demo on this machine.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402

from app.atrisk.detector import run_detector  # noqa: E402
from app.core.langgraph.graph import LangGraphAgent  # noqa: E402
from app.jobs.atrisk_job import run_at_risk_job  # noqa: E402
from app.models.user import User  # noqa: E402
from app.notifications.learner_chat_channel import LearnerChatChannel  # noqa: E402
from app.schemas.progress import LearnerProgress  # noqa: E402
from app.services.database import DatabaseService  # noqa: E402

DEMO_LEARNERS = [
    {"email": "demo.learner.amir@example.com", "password": "DemoLearner_2026!", "username": "Amir (demo)"},
    {"email": "demo.learner.sara@example.com", "password": "DemoLearner_2026!", "username": "Sara (demo)"},
]

# Stand-in for a real prior conversation, so the demo proves append-not-overwrite
# against actual stored history rather than an empty thread.
SEED_TURNS = [
    HumanMessage(content="Hey, I'm a bit behind on this week's tasks, just so you know."),
    AIMessage(content="Thanks for flagging that -- no worries, let me know if you want to talk through a plan."),
]


async def _ensure_learner(db_service: DatabaseService, email: str, password: str, username: str):
    """Get-or-create a real User + a real chat Session with seeded prior turns."""
    user = await db_service.get_user_by_email(email)
    if user is None:
        user = await db_service.create_user(email=email, password=User.hash_password(password), username=username)
        print(f"  created user {email} (id={user.id})")
    else:
        print(f"  reusing existing user {email} (id={user.id})")

    session_id = str(uuid.uuid4())
    await db_service.create_session(session_id, user.id, name="Demo nudge session", username=username)
    print(f"  created session {session_id}")

    agent = LangGraphAgent()
    for message in SEED_TURNS:
        await agent.append_message(session_id, message)
    print(f"  seeded {len(SEED_TURNS)} prior chat turns")

    return user, session_id


def _at_risk_progress(learner_id: str) -> LearnerProgress:
    """A LearnerProgress snapshot deliberately built to trip the at-risk detector.

    2/12 tasks done (progress_ratio ~0.17, under the 0.5 default threshold),
    3 missed deadlines (over the default 2), 9 days inactive (over the
    default 7) -- three independent signals trip, so this isn't riding a
    borderline threshold.
    """
    now = datetime.now(UTC)
    return LearnerProgress(
        learner_id=learner_id,
        cohort_id="cohort_demo",
        as_of=now,
        total_tasks=12,
        completed_tasks=2,
        missed_deadlines=3,
        last_active_at=now - timedelta(days=9),
        recent_feedback=[],
    )


def main() -> None:
    db_service = DatabaseService()
    learner_ids: list[str] = []
    sessions: dict[str, str] = {}

    print("Setting up demo learners (real User + Session + seeded chat history)...")
    for learner in DEMO_LEARNERS:
        user, session_id = asyncio.run(_ensure_learner(db_service, **learner))
        learner_ids.append(str(user.id))
        sessions[str(user.id)] = session_id

    progress_snapshots = [_at_risk_progress(lid) for lid in learner_ids]

    # Sanity check before spending a real job run: confirm these snapshots
    # actually trip the detector, so a silent threshold miss doesn't get
    # mistaken for a channel bug.
    print("\nPreviewing detector output for these learners:")
    for result in run_detector(progress_snapshots):
        status = "AT RISK" if result.signals.at_risk else "not at risk"
        print(f"  learner_id={result.learner_id}: {status} (score={result.signals.score}/4)")

    # NOTE: run_at_risk_job is a plain sync function -- it must NOT be called
    # from inside an active asyncio event loop, because LearnerChatChannel.send()
    # calls asyncio.run() internally to reach the async LangGraph checkpointer.
    # Calling it here, after the asyncio.run() calls above have already
    # returned (so no loop is running), keeps that contract intact.
    print("\nRunning the real at-risk job with sender=LearnerChatChannel()...")
    summary = run_at_risk_job(
        progress_provider=lambda: progress_snapshots,
        sender=LearnerChatChannel(),
    )
    print(
        f"  job done: evaluated={summary.evaluated_count} at_risk={summary.at_risk_count} "
        f"nudges_sent={summary.nudges_sent} (0 here just means the 7-day frequency "
        f"cap already skipped it on a prior run -- see module docstring)"
    )

    print("\nReading back each learner's chat history (proving the nudge appended, not overwrote):")
    for lid, session_id in sessions.items():
        # A fresh LangGraphAgent (and therefore a fresh connection pool) per
        # call, matching _ensure_learner's pattern -- avoids reusing one
        # agent's pool across more than one asyncio.run() call, which is
        # exactly what caused LearnerChatChannel's duplicate-append bug
        # (see app/notifications/learner_chat_channel.py's _get_loop docstring).
        history = asyncio.run(LangGraphAgent().get_chat_history(session_id))
        print(f"\n--- learner_id={lid} / session_id={session_id} ---")
        for turn in history:
            print(f"  [{turn['role']}] {turn['content']}")


if __name__ == "__main__":
    main()
