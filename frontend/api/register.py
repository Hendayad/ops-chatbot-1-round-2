"""Frontend registration API client."""

from typing import Any

import requests

from api.config import BASE_URL


class RegistrationError(RuntimeError):
    """Raised when account registration cannot be completed."""


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

    return f"Registration failed with HTTP {response.status_code}."


def register(email: str, username: str, password: str) -> dict[str, Any]:
    """Register a user through the FastAPI backend."""
    try:
        response = requests.post(
            f"{BASE_URL}/auth/register",
            json={
                "email": email.strip(),
                "username": username.strip(),
                "password": password,
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