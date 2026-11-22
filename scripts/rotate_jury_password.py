#!/usr/bin/env python3
"""Generate/rotate jury credentials without putting plaintext in Git or Compose."""
from __future__ import annotations

import argparse
from hashlib import pbkdf2_hmac
import os
from pathlib import Path
import secrets


ROOT = Path(__file__).resolve().parents[1]


def make_password_hash(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 310_000)
    return f"pbkdf2_sha256:310000:{salt}:{digest.hex()}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--credentials-file", type=Path, required=True,
        help="Private absolute path OUTSIDE the Git repository; file must not already exist.",
    )
    parser.add_argument("--username", default="jury")
    args = parser.parse_args()
    name = args.username
    if not name.isascii() or not name.replace("_", "").isalnum() or len(name) > 64:
        raise SystemExit("Invalid username.")
    destination = args.credentials_file.resolve()
    if ROOT in destination.parents or ROOT == destination:
        raise SystemExit("Credentials must be stored OUTSIDE the repository.")
    env_path = ROOT / ".env"
    if not env_path.exists():
        raise SystemExit("Missing .env; copy .env.example before configuration.")
    password = secrets.token_urlsafe(24)
    hash_value = make_password_hash(password)
    original = env_path.read_text(encoding="utf-8")
    env_values = original.splitlines()
    updates = {
        "FORMFLOW_AUTH_MODE": "on",
        "FORMFLOW_AUTH_USER": name,
        # Colons avoid Docker Compose $ interpolation in .env.
        "FORMFLOW_AUTH_PASSWORD_HASH": hash_value,
    }
    next_lines = []
    for line in env_values:
        key = line.split("=", 1)[0] if "=" in line else ""
        if key in updates:
            continue
        next_lines.append(line)
    next_lines.extend(f"{key}={value}" for key, value in updates.items())
    destination.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    fd = os.open(destination, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as private:
        private.write(f"Login: {name}\nHasło: {password}\n")
    os.chmod(env_path, 0o600)
    temporary = env_path.with_name(".env.jury-temp")
    with temporary.open("w", encoding="utf-8") as target:
        target.write("\n".join(next_lines).rstrip() + "\n")
    os.chmod(temporary, 0o600)
    os.replace(temporary, env_path)
    print(f"Configured jury authentication. Credentials saved at: {destination}")
    print("Restart the API container to load the new password hash.")
    # Never echo the password into logs or tool output.


if __name__ == "__main__":
    main()
