"""One-shot helper: get a bearer token for the at-risk dashboard.

Tries to register the account; if it already exists, logs in instead.
Prints the access_token. Set ATRISK_WRITE_TOKEN_FILE=1 to also save it to
atrisk_token.txt next to this script (gitignored -- never commit that file).

No credentials are hardcoded here -- set them via environment variables
before running, so nobody's personal email/password ends up in git history.

Usage (PowerShell):
    $env:ATRISK_DEMO_EMAIL   = "you@example.com"
    $env:ATRISK_DEMO_PASSWORD = "yourpassword"
    uv run python get_atrisk_token.py

Usage (bash):
    ATRISK_DEMO_EMAIL=you@example.com ATRISK_DEMO_PASSWORD=yourpassword uv run python get_atrisk_token.py

Optional:
    ATRISK_DEMO_USERNAME     -- only used if the account doesn't exist yet
                                and needs to be registered (defaults to "demo_user").
    ATRISK_WRITE_TOKEN_FILE  -- set to "1" to also write the token to
                                atrisk_token.txt (gitignored).
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "http://localhost:8000/api/v1/auth"
EMAIL = os.environ.get("ATRISK_DEMO_EMAIL")
PASSWORD = os.environ.get("ATRISK_DEMO_PASSWORD")
USERNAME = os.environ.get("ATRISK_DEMO_USERNAME", "demo_user")
WRITE_TOKEN_FILE = os.environ.get("ATRISK_WRITE_TOKEN_FILE") == "1"


def _post_json(url: str, payload: dict) -> tuple[int, dict]:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _post_form(url: str, payload: dict) -> tuple[int, dict]:
    data = urllib.parse.urlencode(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def main() -> None:
    if not EMAIL or not PASSWORD:
        print("Set ATRISK_DEMO_EMAIL and ATRISK_DEMO_PASSWORD environment variables first, e.g.:")
        print('  $env:ATRISK_DEMO_EMAIL = "you@example.com"')
        print('  $env:ATRISK_DEMO_PASSWORD = "yourpassword"')
        print("  uv run python get_atrisk_token.py")
        sys.exit(1)

    print(f"Registering {EMAIL} ...")
    status, body = _post_json(
        f"{BASE_URL}/register",
        {"email": EMAIL, "password": PASSWORD, "username": USERNAME},
    )

    token = None
    if status == 200:
        # UserResponse.token is a nested Token object: {"access_token": ..., ...}
        token = (body.get("token") or {}).get("access_token")
        print("Registered a new account.")
    elif status == 400 and "already registered" in json.dumps(body).lower():
        print("Account already exists — logging in instead.")
        status, body = _post_form(
            f"{BASE_URL}/login",
            {"email": EMAIL, "password": PASSWORD, "grant_type": "password"},
        )
        if status == 200:
            # TokenResponse has access_token at the top level.
            token = body.get("access_token")
        else:
            print(f"Login failed ({status}): {body}")
            return
    else:
        print(f"Registration failed ({status}): {body}")
        return

    if not token:
        print("Got a success response but couldn't find the token in it. Full response:")
        print(json.dumps(body, indent=2))
        return

    print("\nAccess token:")
    print(token)

    if WRITE_TOKEN_FILE:
        with open("atrisk_token.txt", "w") as f:
            f.write(token)
        print("\nAlso saved to atrisk_token.txt in this folder (gitignored — do not commit it).")


if __name__ == "__main__":
    main()
