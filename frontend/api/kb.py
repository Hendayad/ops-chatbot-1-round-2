import requests

BASE_URL = "http://127.0.0.1:8000/api/v1"


def get_materials(token):

    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = requests.get(
        f"{BASE_URL}/kb/materials",
        headers=headers
    )

    response.raise_for_status()

    return response.json()


def retire_material(token, material_id):

    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = requests.post(
        f"{BASE_URL}/kb/retire/{material_id}",
        headers=headers
    )

    response.raise_for_status()

    return response.json()