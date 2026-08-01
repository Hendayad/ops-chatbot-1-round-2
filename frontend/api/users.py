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
def get_current_user(token):

    response = requests.get(
        f"{BASE_URL}/users/me",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    print("TOKEN:", token)
    print("STATUS:", response.status_code)
    print("BODY:", response.text)

    response.raise_for_status()

    return response.json()