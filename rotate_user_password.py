"""One-off local helper: set/rotate a user's password directly in the DB.

There's no change-password API endpoint in this app, so this updates
User.hashed_password directly using the same bcrypt hashing the app's
own register/login flow uses (see User.hash_password in app/models/user.py).

Takes the target email and new password via environment variables --
nothing hardcoded, so this is safe to keep in the repo (or just run
once and delete it).

Usage (PowerShell):
    $env:ATRISK_ROTATE_EMAIL = "you@example.com"
    $env:ATRISK_ROTATE_PASSWORD = "your-new-password"
    uv run python rotate_user_password.py

Do NOT paste your new password into chat or anywhere else -- just type
it directly into the $env:ATRISK_ROTATE_PASSWORD line in your terminal.
"""

from __future__ import annotations

import os
import sys

from sqlmodel import select

from app.models.user import User
from app.services.database import DatabaseService

# Merging main in added User.notification_preference, a relationship declared
# by string name ("NotificationPreference"). SQLAlchemy only resolves that
# name if the class has actually been imported somewhere by the time any
# query configures the User mapper -- the live app gets this for free via
# its own import chain (app.main -> app.api.v1.api -> app.prefs.api), but a
# standalone script like this one needs the same import explicitly, or
# querying User blows up with "failed to locate a name ('NotificationPreference')".
from app.models.notification_preference import NotificationPreference  # noqa: F401


def main() -> None:
    email = os.environ.get("ATRISK_ROTATE_EMAIL")
    new_password = os.environ.get("ATRISK_ROTATE_PASSWORD")

    if not email or not new_password:
        print("Set ATRISK_ROTATE_EMAIL and ATRISK_ROTATE_PASSWORD environment variables first, e.g.:")
        print('  $env:ATRISK_ROTATE_EMAIL = "you@example.com"')
        print('  $env:ATRISK_ROTATE_PASSWORD = "your-new-password"')
        print("  uv run python rotate_user_password.py")
        sys.exit(1)

    db_service = DatabaseService()
    with db_service.get_session_maker() as session:
        user = session.exec(select(User).where(User.email == email)).first()
        if user is None:
            print(f"No user found with email={email!r}.")
            return
        user.hashed_password = User.hash_password(new_password)
        session.add(user)
        session.commit()
        print(f"Password updated for {email}. The old password no longer works.")


if __name__ == "__main__":
    main()
