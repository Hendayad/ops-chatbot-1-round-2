import requests
from urllib.parse import quote

from api.config import BASE_URL


class KnowledgeBaseAPIError(RuntimeError):
    """Raised when a Knowledge Base backend request fails."""


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _extract_error(response):
    try:
        payload = response.json()
    except ValueError:
        return f"Backend returned HTTP {response.status_code}."

    detail = payload.get("detail")
    if isinstance(detail, str) and detail.strip():
        return detail.strip()

    return f"Backend returned HTTP {response.status_code}."


def get_materials(token):
    response = requests.get(
        f"{BASE_URL}/kb/materials",
        headers=_headers(token),
        timeout=15,
    )
    if not response.ok:
        raise KnowledgeBaseAPIError(_extract_error(response))
    return response.json()


def get_material(token, material_id):
    safe_id = quote(material_id, safe="/")
    response = requests.get(
        f"{BASE_URL}/kb/materials/{safe_id}",
        headers=_headers(token),
        timeout=15,
    )
    if not response.ok:
        raise KnowledgeBaseAPIError(_extract_error(response))
    return response.json()


def retire_material(token, material_id):
    safe_id = quote(material_id, safe="/")
    response = requests.post(
        f"{BASE_URL}/kb/retire/{safe_id}",
        headers=_headers(token),
        timeout=15,
    )
    if not response.ok:
        raise KnowledgeBaseAPIError(_extract_error(response))
    return response.json()


def get_cohorts(token):
    response = requests.get(
        f"{BASE_URL}/kb/cohorts",
        headers=_headers(token),
        params={"include_disabled": False},
        timeout=15,
    )
    if not response.ok:
        raise KnowledgeBaseAPIError(_extract_error(response))
    return response.json()


def onboard_cohort(token, cohort_id):
    safe_cohort_id = quote(str(cohort_id), safe="")
    response = requests.post(
        f"{BASE_URL}/kb/cohorts/{safe_cohort_id}/onboard",
        headers=_headers(token),
        timeout=60,
    )
    if not response.ok:
        raise KnowledgeBaseAPIError(_extract_error(response))
    return response.json()