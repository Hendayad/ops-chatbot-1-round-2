import requests
from urllib.parse import quote

from api.config import BASE_URL


def get_materials(token):
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BASE_URL}/kb/materials",
        headers=headers,
    )
    response.raise_for_status()
    return response.json()


def get_material(token, material_id):
    headers = {"Authorization": f"Bearer {token}"}
    safe_id = quote(material_id, safe="/")
    response = requests.get(
        f"{BASE_URL}/kb/materials/{safe_id}",
        headers=headers,
    )
    response.raise_for_status()
    return response.json()


def retire_material(token, material_id):
    headers = {"Authorization": f"Bearer {token}"}
    safe_id = quote(material_id, safe="/")
    response = requests.post(
        f"{BASE_URL}/kb/retire/{safe_id}",
        headers=headers,
    )
    response.raise_for_status()
    return response.json()

def get_cohorts(token):
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BASE_URL}/kb/cohorts",
        headers=headers,
    )
    response.raise_for_status()
    return response.json()


def onboard_cohort(token, cohort_id):
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(
        f"{BASE_URL}/kb/cohorts/{cohort_id}/onboard",
        headers=headers,
    )
    response.raise_for_status()
    return response.json()