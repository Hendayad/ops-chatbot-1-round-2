"""Notification preference service."""

from sqlmodel import Session, select

from app.models.notification_preference import NotificationPreference


def get_preferences(
    session: Session,
    user_id: int,
) -> NotificationPreference:
    """Return a user's preferences."""
    prefs = session.exec(select(NotificationPreference).where(NotificationPreference.user_id == user_id)).first()

    if prefs is None:
        prefs = NotificationPreference(user_id=user_id)
        session.add(prefs)
        session.commit()
        session.refresh(prefs)

    return prefs


def update_preferences(
    session: Session,
    user_id: int,
    data,
) -> NotificationPreference:
    """Update preferences."""
    prefs = get_preferences(session, user_id)

    updates = data.model_dump(exclude_unset=True)

    for key, value in updates.items():
        setattr(prefs, key, value)

    session.add(prefs)
    session.commit()
    session.refresh(prefs)

    return prefs
