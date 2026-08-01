from __future__ import annotations

import os
from typing import Any

import requests

BASE_URL = os.getenv(
    "BACKEND_API_URL",
    "http://127.0.0.1:8000/api/v1",
).rstrip("/")

_REQUEST_TIMEOUT_SECONDS = 15


def _auth_headers(token: str) -> dict[str, str]:
    """Build the Bearer-token headers used by ticket requests."""
    if not token or not token.strip():
        raise ValueError("A valid authentication token is required.")

    return {
        "Authorization": f"Bearer {token.strip()}",
        "Accept": "application/json",
    }


def _request(
    method: str,
    path: str,
    *,
    token: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Send an authenticated request to the backend ticket API."""
    try:
        response = requests.request(
            method=method,
            url=f"{BASE_URL}{path}",
            headers=_auth_headers(token),
            params=params,
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.HTTPError as exc:
        detail = "Ticket API request failed."

        try:
            payload = response.json()
            detail = payload.get("detail", detail)
        except (ValueError, AttributeError):
            pass

        raise RuntimeError(
            f"{detail} Status code: {response.status_code}."
        ) from exc
    except requests.RequestException as exc:
        raise RuntimeError(
            "Could not connect to the ticket API."
        ) from exc

    return response.json()


def get_tickets(
    token: str,
    *,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """Return a paginated ticket list, optionally filtered by status."""
    params: dict[str, Any] = {
        "offset": offset,
        "limit": limit,
    }

    if status and status.lower() != "all":
        params["status"] = status.lower()

    return _request(
        "GET",
        "/tickets",
        token=token,
        params=params,
    )


def get_ticket(token: str, ticket_id: str) -> dict[str, Any]:
    """Return the full details of one ticket."""
    if not ticket_id or not ticket_id.strip():
        raise ValueError("ticket_id is required.")

    return _request(
        "GET",
        f"/tickets/{ticket_id.strip()}",
        token=token,
    )


def resolve_ticket(token: str, ticket_id: str) -> dict[str, Any]:
    """Mark one ticket as resolved and return its updated details."""
    if not ticket_id or not ticket_id.strip():
        raise ValueError("ticket_id is required.")

    return _request(
        "PATCH",
        f"/tickets/{ticket_id.strip()}/resolve",
        token=token,
    )