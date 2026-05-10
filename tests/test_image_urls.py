"""Rows with image_url must have usable non-empty paths; optional HTTP check."""
from __future__ import annotations

import pytest

from app.db import execute_query


def _non_empty_image_tables():
    return [
        ("Person", "person_id"),
        ("Dynasty", "dynasty_id"),
        ("Territory", "territory_id"),
        ("Event", "event_id"),
    ]


def test_image_url_non_null_string_when_set():
    for table, pk in _non_empty_image_tables():
        rows = execute_query(
            f"""
            SELECT {pk}, image_url FROM {table}
            WHERE image_url IS NOT NULL
            """
        )
        for _pk, url in rows:
            assert isinstance(url, str)
            assert url.strip() != "", f"{table} {pk}={_pk} has blank image_url"


@pytest.mark.parametrize("check_http", [False, True], ids=["meta_only", "with_http"])
def test_image_urls_optional_http(client, check_http: bool):
    rows: list[tuple] = []
    for table, pk in _non_empty_image_tables():
        part = execute_query(
            f"SELECT %s::text, {pk}, image_url FROM {table} WHERE image_url IS NOT NULL LIMIT 2",
            (table,),
        )
        rows.extend(part)
    if not rows:
        pytest.skip("No image_url rows.")
    if not check_http:
        return
    for _kind, _eid, raw in rows:
        url = (raw or "").strip()
        if url.startswith(("http://", "https://")):
            continue
        path = url
        if path.startswith("/images/"):
            path = path[len("/images/") :]
        elif path.startswith("images/"):
            path = path[len("images/") :]
        rv = client.get(f"/images/{path}")
        assert rv.status_code == 200, f"GET /images/{path} -> {rv.status_code}"
