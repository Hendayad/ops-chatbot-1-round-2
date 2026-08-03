from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc
from sqlmodel import col, select

from app.api.v1.auth import get_current_user
from app.models.escalation_ticket import EscalationTicket
from app.models.user import User, UserRole
from app.models.user_notification import UserNotification
from app.services.database import DatabaseService


router = APIRouter()

db_service = DatabaseService()


@router.get("/")
async def get_notifications(
    current_user: User = Depends(get_current_user),
):

    with db_service.get_session_maker() as session:

        # ---------------------------------
        # Learner notifications
        # ---------------------------------

        if current_user.role == UserRole.LEARNER:

            notifications = session.exec(
                select(UserNotification)
                .where(
                    UserNotification.user_id == str(current_user.id)
                )
                .order_by(
                    desc(col(UserNotification.created_at))
                )
            ).all()

            return notifications


        # ---------------------------------
        # Program Lead + Admin notifications
        # ---------------------------------

        if current_user.role in (
            UserRole.PROGRAM_LEAD,
            UserRole.ADMIN,
        ):

            cutoff = (
                datetime.now(timezone.utc)
                - timedelta(days=2)
            )

            overdue = session.exec(
                select(EscalationTicket)
                .where(
                    EscalationTicket.status == "open"
                )
                .where(
                    EscalationTicket.created_at <= cutoff
                )
                .order_by(
                    col(EscalationTicket.created_at)
                )
            ).all()


            return [
                {
                    "id": ticket.id,
                    "title": "Overdue Ticket",
                    "message": (
                        f"Ticket {ticket.id} has been open "
                        "for more than 2 days."
                    ),
                    "ticket_id": ticket.id,
                    "created_at": ticket.created_at,
                }
                for ticket in overdue
            ]


        # ---------------------------------
        # Unknown role protection
        # ---------------------------------

        raise HTTPException(
            status_code=403,
            detail="Unsupported user role",
        )



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