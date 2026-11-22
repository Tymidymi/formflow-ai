#!/usr/bin/env python3
"""Provision the *official Caddy* Basic Auth without persisting plaintext.

This is a credential provisioning helper, not an authentication implementation.
Caddy verifies credentials on every HTTP request.
"""
from __future__ import annotations

import argparse
from getpass import getpass
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
USERS = ROOT / "data/private/caddy/jury-users.caddy"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", default="jury")
    parser.add_argument("--rotate", action="store_true",
                        help="Replace the existing Caddy credential file.")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", args.username):
        parser.error("Username must be 1-64 alphanumeric / underscore / hyphen characters.")
    if USERS.exists() and not args.rotate:
        parser.error("Credentials already exist; add --rotate to deliberately replace.")
    if not USERS.exists() and args.rotate:
        parser.error("No existing credentials to rotate.")

    password = getpass("Nowe hasło jury (minimum 20 znaków): ")
    confirm = getpass("Potwierdź hasło: ")
    if password != confirm or len(password) < 20:
        parser.error("Passwords do not match or are shorter than 20 characters.")
    if "\n" in password or "\r" in password:
        parser.error("Password must be a single line.")

    # No password in shell history, process argv or logs.
    hashed = subprocess.run(
        ["docker", "run", "--rm", "-i", "caddy:2.11.9-alpine", "caddy",
         "hash-password", "--algorithm", "bcrypt", "--bcrypt-cost", "12"],
        input=(password + "\n").encode(),
        capture_output=True, check=True,
    ).stdout.decode().strip()
    if not re.fullmatch(r"\$2[aby]\$12\$[./A-Za-z0-9]{53}", hashed):
        raise SystemExit("Caddy did not return a supported bcrypt hash.")
    USERS.parent.mkdir(parents=True, exist_ok=True)
    USERS.parent.chmod(0o700)
    fd, path = tempfile.mkstemp(prefix=".jury-", dir=USERS.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as target:
            target.write(args.username + " " + hashed + "\n")
        os.chmod(path, 0o600)
        os.replace(path, USERS)
    finally:
        if os.path.exists(path):
            os.unlink(path)
    print(f"Caddy credentials {'rotated' if args.rotate else 'created'}: {USERS}")
    print("Restart the gateway container to activate the new hash.")
    # Password must never be printed here.


if __name__ == "__main__":
    main()
