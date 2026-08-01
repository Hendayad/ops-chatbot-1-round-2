import requests

BASE_URL = "http://127.0.0.1:8000/api/v1"

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