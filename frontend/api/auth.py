import requests

BASE_URL = "http://127.0.0.1:8000/api/v1"


def login(email, password):
    print("EMAIL:", repr(email))
    print("PASSWORD:", repr(password))
    #print("GRANT:", repr(grant_type))
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={
            "email": email,
            "password": password,
            "grant_type": "password",
        },
    )

    print("Request URL:", response.request.url)
    print("Request Method:", response.request.method)
    print("Status:", response.status_code)
    print("Response:", response.text)
    

    response.raise_for_status()
    return response.json()