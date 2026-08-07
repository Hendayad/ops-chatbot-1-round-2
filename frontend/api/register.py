"""Frontend registration API client."""

from typing import Any

import requests

from api.config import BASE_URL


class RegistrationError(RuntimeError):
    """Raised when account registration cannot be completed."""


class CohortLoadError(RuntimeError):
    """Raised when available cohorts cannot be loaded."""


def _extract_error(response: requests.Response) -> str:
    """Extract a useful FastAPI error message."""
    try:
        payload: dict[str, Any] = response.json()
    except ValueError:
        return f"Backend returned HTTP {response.status_code}."

    errors = payload.get("errors")
    if isinstance(errors, list) and errors:
        messages = []

        for error in errors:
            if not isinstance(error, dict):
                continue

            field = str(error.get("field", "")).strip()
            message = str(error.get("message", "")).strip()

            if field and message:
                messages.append(f"{field}: {message}")
            elif message:
                messages.append(message)

        if messages:
            return "; ".join(messages)

    detail = payload.get("detail")
    if isinstance(detail, str) and detail.strip():
        return detail.strip()

    return f"Request failed with HTTP {response.status_code}."


def get_available_cohorts() -> list[dict[str, str]]:
    """Load the public list of cohorts available for registration."""
    try:
        response = requests.get(
            f"{BASE_URL}/auth/cohorts",
            timeout=10,
        )
    except requests.RequestException as exc:
        raise CohortLoadError(
            f"Could not connect to the backend at {BASE_URL}."
        ) from exc

    if not response.ok:
        raise CohortLoadError(_extract_error(response))

    payload = response.json()
    if not isinstance(payload, list):
        raise CohortLoadError("Backend returned an invalid cohort list.")

    cohorts: list[dict[str, str]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue

        cohort_id = str(item.get("cohort_id", "")).strip()
        name = str(item.get("name", "")).strip()

        if cohort_id and name:
            cohorts.append(
                {
                    "cohort_id": cohort_id,
                    "name": name,
                }
            )

    return cohorts


def register(
    email: str,
    username: str,
    password: str,
    first_name: str,
    last_name: str,
    cohort_id: str,
) -> dict[str, Any]:
    """Register a learner through the FastAPI backend."""
    try:
        response = requests.post(
            f"{BASE_URL}/auth/register",
            json={
                "first_name": first_name.strip(),
                "last_name": last_name.strip(),
                "email": email.strip(),
                "username": username.strip() or None,
                "password": password,
                "cohort_id": cohort_id,
            },
            timeout=15,
        )
    except requests.RequestException as exc:
        raise RegistrationError(
            f"Could not connect to the backend at {BASE_URL}."
        ) from exc

    if not response.ok:
        raise RegistrationError(_extract_error(response))

    return response.json()