"""SQLi resilience, XSS escaping, method guards, auth gates."""
from __future__ import annotations

import pytest


def test_search_sqli_param_returns_ok(client):
    rv = client.get("/search", query_string={"q": "' OR 1=1 --"})
    assert rv.status_code == 200


def test_timeline_numeric_params_ok(client):
    rv = client.get(
        "/timeline",
        query_string={"start_year": "500", "end_year": "2000", "dynasty_id": "1"},
    )
    assert rv.status_code == 200


def test_search_xss_query_escaped(client):
    payload = "<script>alert(1)</script>"
    rv = client.get("/search", query_string={"q": payload})
    assert rv.status_code == 200
    assert b"<script>" not in rv.data
    assert b"&lt;script&gt;" in rv.data


def test_delete_routes_reject_get(admin_client):
    assert admin_client.get("/admin/dynasties/1/delete").status_code == 405
    assert admin_client.get("/admin/backup").status_code == 405
    assert admin_client.get("/admin/clear-db/confirm").status_code == 405


def test_admin_requires_login(client):
    rv = client.get("/admin/", follow_redirects=False)
    assert rv.status_code == 302
    assert "login" in rv.headers.get("Location", "").lower()
