import requests


BASE_URL = "http://127.0.0.1:8000/api/v1"



def get_users(token):

    response = requests.get(
        f"{BASE_URL}/users",
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