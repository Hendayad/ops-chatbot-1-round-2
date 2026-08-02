import requests

from api.config import BASE_URL

def get_reminders(token):
    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = requests.get(
        f"{BASE_URL}/reminders",
        headers=headers
    )

    response.raise_for_status()
    return response.json()