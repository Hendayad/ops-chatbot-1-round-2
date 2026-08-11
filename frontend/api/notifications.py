"""Frontend API helpers for user notifications."""

import requests

from api.config import BASE_URL


# =========================================================
# Headers
# =========================================================

def _headers(token: str) -> dict[str, str]:
    """Build authorization headers."""

    return {
        "Authorization": f"Bearer {token}",
    }


# =========================================================
# Get notifications
# =========================================================

def get_notifications(token: str):
    """
    Get notifications for the currently authenticated user.

    The backend automatically filters notifications by the
    current user's ID.

    Returns:
        list: User notifications.
    """

    response = requests.get(
        f"{BASE_URL}/notifications/",
        headers=_headers(token),
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


# =========================================================
# Get unread count
# =========================================================

def get_unread_count(token: str) -> int:
    """
    Get the number of unread notifications.

    This endpoint is expected to return:

        {
            "count": 3
        }

    Returns:
        int: Number of unread notifications.
    """

    response = requests.get(
        f"{BASE_URL}/notifications/unread-count",
        headers=_headers(token),
        timeout=10,
    )

    response.raise_for_status()

    data = response.json()

    return int(data.get("count", 0))


# =========================================================
# Mark notification as read
# =========================================================

def mark_as_read(
    token: str,
    notification_id: int,
):
    """
    Mark a notification as read.

    IMPORTANT:
    The backend enforces that only learners can perform this
    operation.

    Admins and Program Leads will receive a 403 response if
    they try to use this endpoint.
    """

    response = requests.patch(
        f"{BASE_URL}/notifications/{notification_id}/read",
        headers=_headers(token),
        timeout=10,
    )

    response.raise_for_status()

    return response.json()


# =========================================================
# Get notification preferences
# =========================================================

def get_preferences(token: str):
    """
    Get notification preferences for the current user.

    These preferences are separate from the notification bell.

    Returns:
        dict: Current notification preferences.
    """

    response = requests.get(
        f"{BASE_URL}/notifications/preferences",
        headers=_headers(token),
        timeout=10,
    )

    response.raise_for_status()

    return response.json()


# =========================================================
# Update notification preferences
# =========================================================

def update_preferences(
    token: str,
    preferences: dict,
):
    """
    Update notification preferences for the current user.

    Example:

        {
            "opted_out": False,
            "session_reminders": True,
            "deadline_reminders": True,
            "nudges": True
        }

    Note:
    These preferences affect the reminder/learner notification
    behavior according to the backend implementation. They do
    not change the Admin/Program Lead overdue-ticket rule.
    """

    response = requests.put(
        f"{BASE_URL}/notifications/preferences",
        headers=_headers(token),
        json=preferences,
        timeout=10,
    )

    response.raise_for_status()

    return response.json()
