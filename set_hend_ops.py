"""One-off local helper: flip hend.3ayad@gmail.com to is_ops=True.

Run once after `alembic upgrade head` adds the is_ops column, so the
Ops dashboard's /atrisk/* endpoints (now gated by get_current_ops_user)
don't 403 your own account. Safe to re-run.

Usage:
    uv run python set_hend_ops.py
"""

from sqlmodel import select

from app.models.user import User
from app.services.database import DatabaseService

TARGET_EMAIL = "hend.3ayad@gmail.com"


def main() -> None:
    db_service = DatabaseService()
    with db_service.get_session_maker() as session:
        user = session.exec(select(User).where(User.email == TARGET_EMAIL)).first()
        if user is None:
            print(f"No user found with email={TARGET_EMAIL!r} -- log in once first to create the account.")
            return
        if user.is_ops:
            print(f"{TARGET_EMAIL} is already is_ops=True -- nothing to do.")
            return
        user.is_ops = True
        session.add(user)
        session.commit()
        print(f"Updated {TARGET_EMAIL}: is_ops=True")


if __name__ == "__main__":
    main()
