import requests

BASE_URL = "http://127.0.0.1:8000/api/v1"


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

        print("Register status:", response.status_code)
        print("Register response:", response.text)

        response.raise_for_status()

        return response.json()

    except Exception as e:
        print("Register error:", e)
        return None