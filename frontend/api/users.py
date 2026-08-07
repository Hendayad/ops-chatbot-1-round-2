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


def update_role(token, user_id, role, cohort_id=None):
    payload = {
        "role": role,
        "cohort_id": cohort_id,
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
import requests


from api.config import BASE_URL



def get_users(token):

    response = requests.get(
        f"{BASE_URL}/users/",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    response.raise_for_status()

    return response.json()



def update_role(
    token,
    user_id,
    role
):

    response = requests.patch(
        f"{BASE_URL}/users/{user_id}/role",
        headers={
            "Authorization": f"Bearer {token}"
        },
        json={
            "role": role
        }
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


def get_teammates(token):

    response = requests.get(
        f"{BASE_URL}/users/me/teammates",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )


    response.raise_for_status()

    return response.json()



def get_cohorts(token):
    response = requests.get(
        f"{BASE_URL}/kb/cohorts",   
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    response.raise_for_status()

    return response.json()["cohorts"]