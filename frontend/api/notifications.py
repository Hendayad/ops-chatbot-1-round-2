import requests

BASE_URL = "http://127.0.0.1:8000/api/v1"


def get_preferences(token):

    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = requests.get(
        f"{BASE_URL}/notifications/preferences",
        headers=headers
    )

    response.raise_for_status()

    return response.json()


def update_preferences(token, preferences):

    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = requests.put(
        f"{BASE_URL}/notifications/preferences",
        headers=headers,
        json=preferences
    )

    response.raise_for_status()

    return response.json()
def get_notifications(token):

    response = requests.get(
        f"{BASE_URL}/notifications",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    response.raise_for_status()

    return response.json()


def mark_as_read(
    token,
    notification_id,
):

    response = requests.patch(
        f"{BASE_URL}/notifications/{notification_id}/read",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    response.raise_for_status()

    return response.json()