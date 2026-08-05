import requests

from api.config import BASE_URL


def get_cohorts(token):
    response = requests.get(
        f"{BASE_URL}/kb/cohorts",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    response.raise_for_status()

    return response.json()["cohorts"]