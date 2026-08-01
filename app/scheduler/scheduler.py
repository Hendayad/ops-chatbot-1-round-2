"""Application background scheduler."""

from apscheduler.schedulers.background import BackgroundScheduler

from app.jobs.atrisk_job import run_scheduled_at_risk_job
from app.jobs.reminder_job import run as run_reminder_job
from app.core.logging import logger


scheduler = BackgroundScheduler()


def start_scheduler() -> None:
    """Start background scheduled jobs."""
    scheduler.add_job(
        run_reminder_job,
        trigger="interval",
        minutes=5,
        id="reminder_job",
        replace_existing=True,
    )

    # Idempotent per UTC calendar day (see app.jobs.atrisk_job's module
    # docstring), so an interval trigger is safe even though this
    # conceptually runs "daily" -- re-firing within the same day just
    # re-evaluates and upserts the same day's state instead of duplicating
    # it. Runs against whatever app.atrisk.progress_store currently holds,
    # which is empty (and therefore a no-op) until something real ingests
    # progress data -- see that module's docstring.
    scheduler.add_job(
        run_scheduled_at_risk_job,
        trigger="interval",
        hours=24,
        id="at_risk_job",
        replace_existing=True,
    )

    scheduler.start()

    logger.info("scheduler_started")


def stop_scheduler() -> None:
    """Stop background scheduler."""
    if scheduler.running:
        scheduler.shutdown()

        logger.info("scheduler_stopped")
