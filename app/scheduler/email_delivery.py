"""Email delivery action for reminder notifications."""
import asyncio
import smtplib
from email.message import EmailMessage

from app.core.config import settings
from app.schemas.notification import Notification
from app.services.database import DatabaseService

db_service = DatabaseService()


def send_email_reminder(notification: Notification) -> None:
    """Send a reminder notification via email.

    Resolves notification.recipient_id (a user ID) to a real email address,
    then sends via SMTP. Raises on any failure (missing user, missing email
    config, SMTP error) so tenacity can retry and run_notification can mark
    the notification FAILED if all retries are exhausted.

    Requires SMTP_HOST, SMTP_PORT, SMTP_FROM_EMAIL to be configured.
    """
    user_id = int(notification.recipient_id)
    user = asyncio.run(db_service.get_user(user_id))
    if user is None:
        raise ValueError(f"No user found for recipient_id={notification.recipient_id}")
    if not user.email:
        raise ValueError(f"User {user_id} has no email address on file")

    msg = EmailMessage()
    msg["Subject"] = notification.payload.title
    msg["From"] = settings.SMTP_FROM_EMAIL
    msg["To"] = user.email
    msg.set_content(notification.payload.body)

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
        server.send_message(msg)