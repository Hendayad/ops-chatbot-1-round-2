import requests

from api.config import BASE_URL


def get_users(token):
    response = requests.get(
        f"{BASE_URL}/users",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )
    response.raise_for_status()
    return response.json()


def update_role(token, user_id, role, cohort=None):
    payload = {
        "role": role,
        "cohort": cohort,
    }

    response = requests.patch(
        f"{BASE_URL}/users/{user_id}/role",
        headers={
            "Authorization": f"Bearer {token}"
        },
        json=payload,
    )
    response.raise_for_status()
    return response.json()


def get_current_user(token):
    response = requests.get(
        f"{BASE_URL}/users/me",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )
    response.raise_for_status()
    return response.json()