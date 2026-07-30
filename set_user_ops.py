"""One-off local helper: flip a user's is_ops flag to True.

Run once after `alembic upgrade head` adds the is_ops column, so the
Ops dashboard's /atrisk/* endpoints (gated by get_current_ops_user)
don't 403 the account you pass in. Safe to re-run.

Takes the target email via --email or the ATRISK_OPS_EMAIL environment
variable -- nothing person-specific is hardcoded, so this is safe to
share as a generic repo helper.

Usage:
    uv run python set_user_ops.py --email you@example.com

    # or, via environment variable:
    ATRISK_OPS_EMAIL=you@example.com uv run python set_user_ops.py
"""

from __future__ import annotations

import argparse
import os
import sys

from sqlmodel import select

from app.models.user import User
from app.services.database import DatabaseService


def main() -> None:
    parser = argparse.ArgumentParser(description="Flip a user's is_ops flag to True.")
    parser.add_argument(
        "--email",
        default=os.environ.get("ATRISK_OPS_EMAIL"),
        help="Email of the account to grant ops access to. Falls back to the ATRISK_OPS_EMAIL env var.",
    )
    args = parser.parse_args()

    if not args.email:
        print("Pass --email you@example.com, or set the ATRISK_OPS_EMAIL environment variable.")
        sys.exit(1)

    db_service = DatabaseService()
    with db_service.get_session_maker() as session:
        user = session.exec(select(User).where(User.email == args.email)).first()
        if user is None:
            print(f"No user found with email={args.email!r} -- log in once first to create the account.")
            return
        if user.is_ops:
            print(f"{args.email} is already is_ops=True -- nothing to do.")
            return
        user.is_ops = True
        session.add(user)
        session.commit()
        print(f"Updated {args.email}: is_ops=True")


if __name__ == "__main__":
    main()
