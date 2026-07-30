"""One-shot helper: get a bearer token for the at-risk dashboard.

Tries to register the account; if it already exists, logs in instead.
Prints the access_token and also saves it to atrisk_token.txt next to
this script, so you can just open that file and copy it.

Usage:
    uv run python get_atrisk_token.py
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "http://localhost:8000/api/v1/auth"
EMAIL = "hend.3ayad@gmail.com"
PASSWORD = "Ahmed_2020!"
USERNAME = "HendAyad"


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

    with open("atrisk_token.txt", "w") as f:
        f.write(token)
    print("\nAlso saved to atrisk_token.txt in this folder.")


if __name__ == "__main__":
    main()
