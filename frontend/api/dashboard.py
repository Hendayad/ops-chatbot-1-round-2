import requests

BASE_URL = "http://127.0.0.1:8000/api/v1"


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

        print("Dashboard API Status:", response.status_code)
        print("Dashboard API Response:", response.text)

        response.raise_for_status()

        return response.json()

    except requests.exceptions.RequestException as e:
        print("Dashboard API Error:", e)
        return None