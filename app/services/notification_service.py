from sqlmodel import Session

from app.models.user_notification import UserNotification


def create_notification(
    session: Session,
    *,
    user_id: str,
    title: str,
    message: str,
    category: str,
) -> UserNotification:
    """Create an in-app notification."""
    notification = UserNotification(
        user_id=user_id,
        title=title,
        message=message,
        category=category,
    )

    session.add(notification)
    session.commit()
    session.refresh(notification)

    return notification