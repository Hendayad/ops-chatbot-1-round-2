import requests

from api.config import BASE_URL


def get_tickets(token):
    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = requests.get(
        f"{BASE_URL}/tickets",
        headers=headers
    )

    response.raise_for_status()

    return response.json()
def resolve_ticket(token, ticket_id):

    response = requests.patch(
        f"{BASE_URL}/tickets/{ticket_id}/resolve",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    response.raise_for_status()

    return response.json()