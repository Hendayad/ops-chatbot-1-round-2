import asyncio

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.v1.auth import get_current_user
from app.services.database import DatabaseService

client = TestClient(app)
db_service = DatabaseService()

TEST_EMAIL = "notification_pref_test@example.com"


@pytest.fixture(autouse=True)
def cleanup():
    asyncio.run(db_service.delete_user_by_email(TEST_EMAIL))


@pytest.fixture
def authenticated_user():
    user = asyncio.run(
        db_service.create_user(
            email=TEST_EMAIL,
            password="password",
            username="pref_user",
        )
    )

    async def override():
        return user

    app.dependency_overrides[get_current_user] = override

    yield user

    app.dependency_overrides.clear()


def test_get_default_preferences(authenticated_user):
    response = client.get("/api/v1/notifications/preferences")

    assert response.status_code == 200

    data = response.json()

    assert data["opted_out"] is False
    assert data["session_reminders"] is True
    assert data["deadline_reminders"] is True
    assert data["nudges"] is True


def test_update_preferences(authenticated_user):
    response = client.put(
        "/api/v1/notifications/preferences",
        json={
            "opted_out": False,
            "session_reminders": False,
            "deadline_reminders": True,
            "nudges": False,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["session_reminders"] is False
    assert data["deadline_reminders"] is True
    assert data["nudges"] is False
    assert data["opted_out"] is False


def test_full_opt_out(authenticated_user):
    response = client.put(
        "/api/v1/notifications/preferences",
        json={
            "opted_out": True,
            "session_reminders": False,
            "deadline_reminders": False,
            "nudges": False,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["opted_out"] is True


def test_preferences_persist(authenticated_user):
    client.put(
        "/api/v1/notifications/preferences",
        json={
            "opted_out": False,
            "session_reminders": False,
            "deadline_reminders": False,
            "nudges": True,
        },
    )

    response = client.get("/api/v1/notifications/preferences")

    assert response.status_code == 200

    data = response.json()

    assert data["session_reminders"] is False
    assert data["deadline_reminders"] is False
    assert data["nudges"] is True


def test_requires_auth():
    app.dependency_overrides.clear()

    response = client.get("/api/v1/notifications/preferences")

    assert response.status_code in (401, 403)
