"""Email delivery action for reminder notifications."""

import asyncio
import smtplib
from email.message import EmailMessage

from app.core.config import settings
from app.schemas.notification import Notification
from app.services.database import database_service

db_service = database_service


def send_email_reminder(notification: Notification) -> None:
    print("=== EMAIL DELIVERY STARTED ===")

    user_id = int(notification.recipient_id)
    print("Looking up user:", user_id)

    user = asyncio.run(db_service.get_user(user_id))
    print("User:", user)

    if user is None:
        raise ValueError(f"No user found for recipient_id={notification.recipient_id}")

    print("Email:", user.email)
    if not user.email:
        raise ValueError("User has no email address")

    msg = EmailMessage()
    msg["Subject"] = notification.payload.title
    msg["From"] = settings.SMTP_FROM_EMAIL
    msg["To"] = user.email
    msg.set_content(notification.payload.body)

    print("Connecting to SMTP...")

    with smtplib.SMTP(
        settings.SMTP_HOST,
        settings.SMTP_PORT,
        timeout=10,
    ) as server:
        server.starttls()
        print("TLS OK")

        try:
            server.login(
                settings.SMTP_USERNAME,
                settings.SMTP_PASSWORD,
            )
            print("Login OK")
        except Exception as e:
            print("LOGIN FAILED:", repr(e))
            raise

        server.send_message(msg)
        print("Email sent!")
