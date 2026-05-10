from __future__ import annotations

import getpass
import sys

from werkzeug.security import generate_password_hash

from app.db import execute_query


def main() -> int:
    username = input("Admin username [admin]: ").strip() or "admin"
    password = getpass.getpass("Admin password: ")
    confirm = getpass.getpass("Confirm password: ")
    if not password or password != confirm:
        print("Passwords do not match or are empty.", file=sys.stderr)
        return 2

    # Werkzeuge's generate_password_hash produces a strong hash compatible with check_password_hash.
    password_hash = generate_password_hash(password)

    existing = execute_query("SELECT user_id FROM User_Account WHERE username = %s", (username,))
    if existing:
        print(f"User '{username}' already exists (user_id={existing[0][0]}).", file=sys.stderr)
        return 1

    execute_query(
        """
        INSERT INTO User_Account (username, password, role, is_active)
        VALUES (%s, %s, 'admin', TRUE)
        """,
        (username, password_hash),
    )
    print(f"Created admin user '{username}'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

