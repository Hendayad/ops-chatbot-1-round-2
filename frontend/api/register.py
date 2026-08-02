import requests

from api.config import BASE_URL


def register(email, username, password):

    try:
        response = requests.post(
            f"{BASE_URL}/auth/register",
            json={
                "email": email,
                "username": username,
                "password": password,
            }
        )


        response.raise_for_status()

        return response.json()

    except Exception as e:
        return None