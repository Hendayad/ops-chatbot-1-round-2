import requests

from api.config import BASE_URL

def login(email, password):
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={
            "email": email,
            "password": password,
            "grant_type": "password",
        },
    )

    

    response.raise_for_status()
    return response.json()