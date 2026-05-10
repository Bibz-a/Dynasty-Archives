"""
Shared pytest fixtures: real PostgreSQL (DB_* / DATABASE_URL), mocked Supabase + Firebase Admin init.

Run from repo root:  pytest tests/ -v
Requires: DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, SECRET_KEY, and Firebase env strings
(in secrets/.env or legacy .env). secrets/serviceAccountKey.json may be absent if Certificate is mocked below.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from werkzeug.security import generate_password_hash

# ---------------------------------------------------------------------------
# Patch external SDKs before any app import pulls supabase_client / firebase.
# ---------------------------------------------------------------------------
_fake_supabase = MagicMock(name="supabase_client")
_supabase_p = patch("supabase.create_client", return_value=_fake_supabase)
_supabase_p.start()

_orig_exists = os.path.exists


def _exists_patch(path: str | bytes | int) -> bool:
    p = os.fspath(path)
    norm = p.replace("\\", "/")
    if norm.endswith("serviceAccountKey.json") and not _orig_exists(p):
        return True
    return _orig_exists(p)


_exists_p = patch("os.path.exists", side_effect=_exists_patch)
_exists_p.start()

_cert_p = patch("firebase_admin.credentials.Certificate", return_value=MagicMock())
_init_p = patch("firebase_admin.initialize_app", return_value=MagicMock())
_cert_p.start()
_init_p.start()


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    _init_p.stop()
    _cert_p.stop()
    _exists_p.stop()
    _supabase_p.stop()


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def app(repo_root: Path):
    """Flask app: testing mode, no CSRF, correct login redirect."""
    os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
    os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-role-key")
    os.environ.setdefault("FIREBASE_API_KEY", "test-api-key")
    os.environ.setdefault("FIREBASE_AUTH_DOMAIN", "test.firebaseapp.com")
    os.environ.setdefault("FIREBASE_PROJECT_ID", "test-project")
    os.environ.setdefault("FIREBASE_DATABASE_URL", "https://test-project.firebaseio.com")
    os.environ.setdefault(
        "FIREBASE_SERVICE_ACCOUNT_JSON",
        str(repo_root / "secrets" / "serviceAccountKey.json"),
    )

    from urllib.parse import quote_plus

    if not (os.getenv("DATABASE_URL") or "").strip():
        host = os.environ.get("DB_HOST", "localhost")
        db = os.environ.get("DB_NAME", "postgres")
        user = os.environ.get("DB_USER", "postgres")
        pwd = os.environ.get("DB_PASSWORD", "")
        port = os.environ.get("DB_PORT", "5432")
        os.environ["DATABASE_URL"] = f"postgresql://{quote_plus(user)}:{quote_plus(pwd)}@{host}:{port}/{db}"

    from app import create_app
    from app.routes.auth import limiter

    flask_app = create_app()
    flask_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
    )
    flask_app.login_manager.login_view = "auth.login"
    limiter.enabled = False
    return flask_app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture(scope="session")
def test_user_credentials():
    """Stable usernames for session-scoped login clients."""
    suffix = uuid.uuid4().hex[:8]
    return {
        "admin_username": f"pytest_admin_{suffix}",
        "admin_password": "PytestAdmin!8chars",
        "viewer_username": f"pytest_viewer_{suffix}",
        "viewer_password": "PytestView!8chars",
    }


@pytest.fixture(scope="session")
def test_user_ids(app, test_user_credentials):  # noqa: ARG001
    from app.db import execute_query

    creds = test_user_credentials
    admin_hash = generate_password_hash(creds["admin_password"])
    viewer_hash = generate_password_hash(creds["viewer_password"])

    admin_rows = execute_query(
        """
        INSERT INTO User_Account (username, password, role, is_active, email)
        VALUES (%s, %s, 'admin', TRUE, %s)
        RETURNING user_id
        """,
        (creds["admin_username"], admin_hash, f"{creds['admin_username']}@pytest.local"),
    )
    viewer_rows = execute_query(
        """
        INSERT INTO User_Account (username, password, role, is_active, email)
        VALUES (%s, %s, 'viewer', TRUE, %s)
        RETURNING user_id
        """,
        (creds["viewer_username"], viewer_hash, f"{creds['viewer_username']}@pytest.local"),
    )
    ids = {"admin_id": int(admin_rows[0][0]), "viewer_id": int(viewer_rows[0][0])}

    yield ids

    execute_query("DELETE FROM User_Account WHERE user_id IN (%s, %s)", (ids["admin_id"], ids["viewer_id"]))


@pytest.fixture()
def admin_client(app, test_user_credentials, test_user_ids):
    c = app.test_client()
    c.post(
        "/login",
        data={
            "username": test_user_credentials["admin_username"],
            "password": test_user_credentials["admin_password"],
        },
    )
    return c


@pytest.fixture()
def viewer_client(app, test_user_credentials, test_user_ids):
    c = app.test_client()
    c.post(
        "/login",
        data={
            "username": test_user_credentials["viewer_username"],
            "password": test_user_credentials["viewer_password"],
        },
    )
    return c


@pytest.fixture()
def db_conn():
    """Direct psycopg2 connection for CALL / raw checks (same DB as app)."""
    import psycopg2
    from config import Config

    conn = psycopg2.connect(
        host=Config.DB_HOST,
        dbname=Config.DB_NAME,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
    )
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture()
def any_dynasty_id():
    from app.db import execute_query

    rows = execute_query("SELECT dynasty_id FROM Dynasty ORDER BY dynasty_id LIMIT 1")
    if not rows:
        pytest.skip("Database has no Dynasty row — seed data required for this test.")
    return int(rows[0][0])


@pytest.fixture()
def any_person_id():
    from app.db import execute_query

    rows = execute_query("SELECT person_id FROM Person ORDER BY person_id LIMIT 1")
    if not rows:
        pytest.skip("Database has no Person row — seed data required.")
    return int(rows[0][0])


@pytest.fixture()
def any_war_event_id():
    from app.db import execute_query

    rows = execute_query(
        "SELECT event_id FROM Event WHERE type::text IN ('war','battle') LIMIT 1"
    )
    if not rows:
        pytest.skip("No war/battle event in DB.")
    return int(rows[0][0])
