import requests

from api.config import BASE_URL


def send_message(token, messages):
    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = requests.post(
        f"{BASE_URL}/chatbot/chat",
        headers=headers,
        json={
            "messages": messages
        }
    )

    response.raise_for_status()

    return response.json()


def get_messages(token):
    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = requests.get(
        f"{BASE_URL}/chatbot/messages",
        headers=headers
    )

    response.raise_for_status()

    return response.json()


def clear_messages(token):
    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = requests.delete(
        f"{BASE_URL}/chatbot/messages",
        headers=headers
    )

    response.raise_for_status()

    return response.json()