"""Authentication against real User_Account rows."""
from __future__ import annotations

import pytest

from app.db import execute_query


def test_login_wrong_password(client, test_user_credentials, test_user_ids):  # noqa: ARG001
    rv = client.post(
        "/login",
        data={
            "username": test_user_credentials["admin_username"],
            "password": "wrong-password-xx",
        },
        follow_redirects=False,
    )
    assert rv.status_code == 302
    assert rv.headers.get("Location", "").endswith("/login")


def test_login_inactive_rejected(client, test_user_credentials, test_user_ids):
    uid = test_user_ids["viewer_id"]
    execute_query("UPDATE User_Account SET is_active = FALSE WHERE user_id = %s", (uid,))
    try:
        rv = client.post(
            "/login",
            data={
                "username": test_user_credentials["viewer_username"],
                "password": test_user_credentials["viewer_password"],
            },
            follow_redirects=False,
        )
        assert rv.status_code == 302
        assert "/login" in rv.headers.get("Location", "")
    finally:
        execute_query("UPDATE User_Account SET is_active = TRUE WHERE user_id = %s", (uid,))


def test_login_google_sentinel_rejected(client):
    execute_query("DELETE FROM User_Account WHERE username = %s", ("__pytest_google_only__",))
    execute_query(
        """
        INSERT INTO User_Account (username, password, role, is_active, email)
        VALUES (%s, 'GOOGLE_AUTH', 'viewer', TRUE, %s)
        """,
        ("__pytest_google_only__", "pytest_google@test.local"),
    )
    try:
        rv = client.post(
            "/login",
            data={"username": "__pytest_google_only__", "password": "anything"},
            follow_redirects=False,
        )
        assert rv.status_code == 302
        assert "/login" in rv.headers.get("Location", "")
    finally:
        execute_query("DELETE FROM User_Account WHERE username = %s", ("__pytest_google_only__",))


def test_admin_redirects_to_admin_dashboard(client, test_user_credentials, test_user_ids):  # noqa: ARG001
    rv = client.post(
        "/login",
        data={
            "username": test_user_credentials["admin_username"],
            "password": test_user_credentials["admin_password"],
        },
        follow_redirects=False,
    )
    assert rv.status_code == 302
    assert "/admin/" in rv.headers.get("Location", "")


def test_viewer_redirects_to_home(client, test_user_credentials, test_user_ids):  # noqa: ARG001
    rv = client.post(
        "/login",
        data={
            "username": test_user_credentials["viewer_username"],
            "password": test_user_credentials["viewer_password"],
        },
        follow_redirects=False,
    )
    assert rv.status_code == 302
    loc = rv.headers.get("Location", "")
    assert loc.endswith("/") or loc.rstrip("/").endswith("localhost")


def test_last_login_updates(client, test_user_credentials, test_user_ids):
    uid = test_user_ids["admin_id"]
    execute_query("UPDATE User_Account SET last_login = NULL WHERE user_id = %s", (uid,))
    client.post(
        "/login",
        data={
            "username": test_user_credentials["admin_username"],
            "password": test_user_credentials["admin_password"],
        },
    )
    rows = execute_query("SELECT last_login FROM User_Account WHERE user_id = %s", (uid,))
    assert rows and rows[0][0] is not None


def test_logout_clears_session(client, test_user_credentials, test_user_ids, any_person_id: int):  # noqa: ARG001
    client.post(
        "/login",
        data={
            "username": test_user_credentials["viewer_username"],
            "password": test_user_credentials["viewer_password"],
        },
    )
    rv = client.get("/logout", follow_redirects=False)
    assert rv.status_code == 302
    rv2 = client.get(f"/rulers/{any_person_id}", follow_redirects=False)
    assert rv2.status_code == 200
