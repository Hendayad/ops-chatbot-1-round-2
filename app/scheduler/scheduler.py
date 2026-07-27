"""Application background scheduler."""

from apscheduler.schedulers.background import BackgroundScheduler

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

    scheduler.start()

    logger.info("scheduler_started")


def stop_scheduler() -> None:
    """Stop background scheduler."""
    if scheduler.running:
        scheduler.shutdown()

        logger.info("scheduler_stopped")