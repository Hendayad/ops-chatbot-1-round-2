"""Application background scheduler."""

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.logging import logger

from app.jobs.atrisk_job import (
    run_scheduled_at_risk_job,
)

from app.jobs.reminder_job import (
    run as run_reminder_job,
)

from app.jobs.overdue_ticket_notification_job import (
    run as run_overdue_ticket_notification_job,
)


scheduler = BackgroundScheduler()


def start_scheduler() -> None:
    """Start background scheduled jobs."""

    # ========================================================
    # Reminder job
    # ========================================================

    scheduler.add_job(
        run_reminder_job,
        trigger="interval",
        minutes=5,
        id="reminder_job",
        replace_existing=True,
    )

    # ========================================================
    # At-risk job
    # ========================================================

    scheduler.add_job(
        run_scheduled_at_risk_job,
        trigger="interval",
        hours=24,
        id="at_risk_job",
        replace_existing=True,
    )

    # ========================================================
    # Overdue escalation notification job
    # ========================================================

    scheduler.add_job(
        run_overdue_ticket_notification_job,
        trigger="interval",
        minutes=5,
        id="overdue_ticket_notification_job",
        replace_existing=True,
    )

    # ========================================================
    # Start scheduler
    # ========================================================

    scheduler.start()

    logger.info("scheduler_started")


def stop_scheduler() -> None:
    """Stop background scheduler."""

    if scheduler.running:
        scheduler.shutdown()

        logger.info("scheduler_stopped")
