import requests

from api.config import BASE_URL


def get_dashboard_metrics(token):
    """
    Fetch dashboard metrics from FastAPI backend.
    """

    headers = {
        "Authorization": f"Bearer {token}"
    }

    try:
        response = requests.get(
            f"{BASE_URL}/dashboards/metrics",
            headers=headers
        )


        response.raise_for_status()

        return response.json()

    except requests.exceptions.RequestException as e:
        return None