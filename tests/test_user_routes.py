"""Public user-facing routes (200s, redirects for missing ids, filters)."""
from __future__ import annotations

import re

import pytest

from app.db import execute_query

PUBLIC_GET_PATHS = [
    "/",
    "/rulers",
    "/dynasties",
    "/events",
    "/timeline",
    "/territories",
    "/wars",
    "/stats",
    "/search",
    "/login",
    "/register",
]


def test_public_pages_return_200(client):
    for path in PUBLIC_GET_PATHS:
        rv = client.get(path)
        assert rv.status_code == 200, f"{path} returned {rv.status_code}"


def test_dynasty_detail_with_real_id(client, any_dynasty_id: int):
    rv = client.get(f"/dynasties/{any_dynasty_id}")
    assert rv.status_code == 200


def test_ruler_detail_with_real_id(client, any_person_id: int):
    rv = client.get(f"/rulers/{any_person_id}")
    assert rv.status_code == 200


def test_ruler_not_found_redirects(client):
    rv = client.get("/rulers/999999999", follow_redirects=False)
    assert rv.status_code == 302
    assert "/rulers" in rv.headers.get("Location", "")


def test_dynasty_not_found_redirects(client):
    rv = client.get("/dynasties/999999999", follow_redirects=False)
    assert rv.status_code == 302
    assert "/dynasties" in rv.headers.get("Location", "")


def test_search_with_real_data(client):
    row = execute_query("SELECT full_name FROM Person LIMIT 1")
    if not row:
        pytest.skip("No persons for search.")
    token = str(row[0][0])[:8]
    rv = client.get("/search", query_string={"q": token})
    assert rv.status_code == 200
    assert token.encode() in rv.data


def test_timeline_filters_by_year(client):
    rows = execute_query(
        """
        SELECT EXTRACT(YEAR FROM event_date)::int AS y
        FROM Event WHERE event_date IS NOT NULL
        ORDER BY event_date LIMIT 1
        """
    )
    if not rows:
        pytest.skip("No dated events.")
    y = int(rows[0][0])
    rv = client.get("/timeline", query_string={"start_year": y, "end_year": y})
    assert rv.status_code == 200


def test_events_filter_by_type(client):
    rows = execute_query("SELECT type::text FROM Event WHERE type::text = 'war' LIMIT 1")
    if not rows:
        pytest.skip("No war events.")
    rv = client.get("/events", query_string={"type": "war"})
    assert rv.status_code == 200


def test_wars_page_only_war_and_battle_rows(client):
    rv = client.get("/wars")
    assert rv.status_code == 200
    ids = re.findall(r"/wars/(\d+)", rv.get_data(as_text=True))
    if not ids:
        pytest.skip("No wars listed on /wars.")
    bad = execute_query(
        """
        SELECT COUNT(*) FROM Event
        WHERE event_id = ANY(%s) AND type::text NOT IN ('war', 'battle')
        """,
        ([int(x) for x in ids[:50]],),
    )
    assert int(bad[0][0]) == 0


def test_vw_wars_and_battles_matches_public_wars_logic():
    bad = execute_query(
        """
        SELECT COUNT(*) FROM vw_wars_and_battles WHERE type::text NOT IN ('war', 'battle')
        """
    )
    assert int(bad[0][0]) == 0
