from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc
from sqlmodel import col, select

from app.api.v1.auth import get_current_user
from app.models.escalation_ticket import EscalationTicket
from app.models.user import User, UserRole
from app.models.user_notification import UserNotification
from app.services.database import database_service


router = APIRouter()

db_service = database_service

import traceback

@router.get("/")
async def get_notifications(
    current_user: User = Depends(get_current_user),
):
    try:
        print("User:", current_user.id, current_user.role)

        with db_service.get_session_maker() as session:

            notifications = session.exec(
                select(UserNotification)
                .where(UserNotification.user_id == str(current_user.id))
                .order_by(desc(col(UserNotification.created_at)))
            ).all()

            print("Notifications:", notifications)

            return notifications

    except Exception:
        traceback.print_exc()
        raise


@router.patch("/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
):

    with db_service.get_session_maker() as session:

        notification = session.get(
            UserNotification,
            notification_id,
        )


        if (
            notification is None
            or notification.user_id != str(current_user.id)
        ):
            raise HTTPException(
                status_code=404,
                detail="Notification not found",
            )


        notification.is_read = True

        session.add(notification)
        session.commit()


        return {
            "message": "updated"
        }