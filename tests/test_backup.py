"""Backup helpers and route wiring (pg_dump mocked; Firebase/Supabase mocked globally in conftest)."""
from __future__ import annotations

import base64

import psycopg2
from unittest.mock import MagicMock, patch

from app.routes.admin import clean_pg_dump

_real_connect = psycopg2.connect


def _make_connect_fake(captured: dict):
    def _connect_fake(*args, **kwargs):
        """Only mock positional DSN connects (restore path); delegate keyword connects to real DB."""
        if args and isinstance(args[0], str) and args[0].lower().startswith("postgres"):
            conn = MagicMock()
            captured["conn"] = conn
            cur = MagicMock()
            conn.cursor.return_value = cur
            return conn
        return _real_connect(*args, **kwargs)

    return _connect_fake


def test_clean_pg_dump_strips_restrict_lines():
    raw = "\\restrict\nINSERT INTO x VALUES (1);\n\\unrestrict\nSELECT 1;\n"
    out = clean_pg_dump(raw)
    assert "\\restrict" not in out
    assert "\\unrestrict" not in out
    assert "INSERT INTO x" in out


@patch("app.routes.admin.get_supabase_client")
@patch("app.routes.admin._dump_table")
@patch("firebase_admin.db.reference")
def test_backup_post_uploads_to_firebase_and_supabase(mock_ref, mock_dump, mock_sb, admin_client):
    mock_dump.side_effect = lambda table, _url: (
        f"INSERT INTO {table} (name) VALUES ('pytest_{table}');\n"
        if table == "dynasty"
        else ""
    )
    ref_inst = MagicMock()
    mock_ref.return_value = ref_inst
    bucket = MagicMock()
    mock_sb.return_value.storage.from_.return_value = bucket

    rv = admin_client.post("/admin/backup", data={})
    assert rv.status_code == 302
    ref_inst.set.assert_called_once()
    assert bucket.upload.called
    payload = ref_inst.set.call_args[0][0]
    assert "tables" in payload
    assert "dynasty" in payload["tables"]
    b64 = payload["tables"]["dynasty"]["content_b64"]
    sql = base64.b64decode(b64.encode()).decode("utf-8")
    assert "pytest_dynasty" in sql


@patch("firebase_admin.db.reference")
def test_firebase_restore_applies_truncate_and_inserts(mock_ref, admin_client, test_user_credentials):
    """Safe: restore's positional-DSN connection is mocked; real DB still used for login/password checks."""
    tables_payload = {
        "dynasty": {
            "content_b64": base64.b64encode(
                b"INSERT INTO dynasty (name) VALUES ('restore_pytest');"
            ).decode("ascii")
        }
    }
    mock_ref.return_value.get.return_value = {
        "metadata": {"folder": "pytest_folder"},
        "tables": tables_payload,
    }

    captured: dict = {}
    with patch("psycopg2.connect", side_effect=_make_connect_fake(captured)):
        admin_client.post(
            "/admin/backups/firebase/pytest_key/restore",
            data={"password": test_user_credentials["admin_password"]},
        )

    conn = captured["conn"]
    cur = conn.cursor.return_value
    stmts = [c[0][0] for c in cur.execute.call_args_list if c[0]]
    joined = " ".join(stmts).upper()
    assert "TRUNCATE" in joined
    assert any("INSERT" in s.upper() for s in stmts)
    assert stmts and "AUDIT_LOG" in stmts[-1].upper()
    conn.commit.assert_called_once()
