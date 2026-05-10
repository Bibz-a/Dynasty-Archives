"""Admin CRUD against real DB with cleanup."""
from __future__ import annotations

import uuid

import pytest

from app.db import execute_query


@pytest.fixture()
def unique_suffix():
    return uuid.uuid4().hex[:8]


def test_dynasty_crud_and_validation(admin_client, unique_suffix: str):
    name = f"PyTest Dynasty {unique_suffix}"
    rv = admin_client.post(
        "/admin/dynasties/add",
        data={"name": "", "start_year": "", "end_year": "", "description": ""},
        follow_redirects=False,
    )
    assert rv.status_code == 302

    rv = admin_client.post(
        "/admin/dynasties/add",
        data={
            "name": name,
            "start_year": "1000",
            "end_year": "1100",
            "description": "pytest",
        },
        follow_redirects=False,
    )
    assert rv.status_code == 302
    rows = execute_query("SELECT dynasty_id FROM Dynasty WHERE name = %s", (name,))
    assert rows
    dynasty_id = int(rows[0][0])

    rv = admin_client.post(
        f"/admin/dynasties/{dynasty_id}/edit",
        data={
            "name": name + " Updated",
            "start_year": "1001",
            "end_year": "1101",
            "description": "pytest2",
        },
        follow_redirects=False,
    )
    assert rv.status_code == 302
    updated = execute_query(
        "SELECT name, start_year FROM Dynasty WHERE dynasty_id = %s", (dynasty_id,)
    )
    assert updated[0][0] == name + " Updated"
    assert int(updated[0][1]) == 1001

    rv = admin_client.post(
        f"/admin/dynasties/{dynasty_id}/delete",
        data={},
        follow_redirects=False,
    )
    assert rv.status_code == 302
    gone = execute_query("SELECT 1 FROM Dynasty WHERE dynasty_id = %s", (dynasty_id,))
    assert not gone


def test_person_crud(admin_client, unique_suffix: str):
    drows = execute_query(
        """
        INSERT INTO Dynasty (name, start_year, end_year)
        VALUES (%s, 900, 950)
        RETURNING dynasty_id
        """,
        (f"PyTest Person Dynasty {unique_suffix}",),
    )
    dynasty_id = int(drows[0][0])
    try:
        full_name = f"PyTest Ruler {unique_suffix}"
        rv = admin_client.post(
            "/admin/persons/add",
            data={
                "full_name": full_name,
                "dynasty_id": str(dynasty_id),
                "title": "King",
                "capital": "Testburg",
                "start_date": "0900-01-01",
                "end_date": "0920-01-01",
            },
            follow_redirects=False,
        )
        assert rv.status_code == 302
        prow = execute_query(
            "SELECT person_id FROM Person WHERE full_name = %s AND dynasty_id = %s",
            (full_name, dynasty_id),
        )
        assert prow
        person_id = int(prow[0][0])
        rrow = execute_query("SELECT 1 FROM Reign WHERE person_id = %s", (person_id,))
        assert rrow

        rv = admin_client.post(
            f"/admin/persons/{person_id}/edit",
            data={
                "full_name": full_name + " II",
                "dynasty_id": str(dynasty_id),
            },
            follow_redirects=False,
        )
        assert rv.status_code == 302
        assert (
            execute_query(
                "SELECT full_name FROM Person WHERE person_id = %s", (person_id,)
            )[0][0]
            == full_name + " II"
        )

        admin_client.post(f"/admin/persons/{person_id}/delete", data={})
        assert not execute_query(
            "SELECT 1 FROM Person WHERE person_id = %s", (person_id,)
        )
    finally:
        execute_query("DELETE FROM Dynasty WHERE dynasty_id = %s", (dynasty_id,))


def test_person_missing_required(admin_client, unique_suffix: str):
    drows = execute_query(
        "INSERT INTO Dynasty (name) VALUES (%s) RETURNING dynasty_id",
        (f"PyTest Val Dynasty {unique_suffix}",),
    )
    did = int(drows[0][0])
    try:
        rv = admin_client.post(
            "/admin/persons/add",
            data={"full_name": "", "dynasty_id": str(did)},
            follow_redirects=False,
        )
        assert rv.status_code == 302
    finally:
        execute_query("DELETE FROM Dynasty WHERE dynasty_id = %s", (did,))


def test_event_crud(admin_client, unique_suffix: str):
    name = f"PyTest Event {unique_suffix}"
    rv = admin_client.post(
        "/admin/events/add",
        data={
            "name": name,
            "type": "political",
            "event_date": "1066-10-14",
        },
        follow_redirects=False,
    )
    assert rv.status_code == 302
    erow = execute_query("SELECT event_id FROM Event WHERE name = %s", (name,))
    assert erow
    eid = int(erow[0][0])

    rv = admin_client.post(
        f"/admin/events/{eid}/edit",
        data={
            "name": name + " X",
            "type": "treaty",
            "event_date": "1067-01-01",
        },
        follow_redirects=False,
    )
    assert rv.status_code == 302
    assert (
        execute_query("SELECT name, type::text FROM Event WHERE event_id = %s", (eid,))[
            0
        ][0]
        == name + " X"
    )

    admin_client.post(f"/admin/events/{eid}/delete", data={})
    assert not execute_query("SELECT 1 FROM Event WHERE event_id = %s", (eid,))


def test_event_validation_missing_type(admin_client, unique_suffix: str):
    rv = admin_client.post(
        "/admin/events/add",
        data={"name": f"Bad {unique_suffix}", "type": ""},
        follow_redirects=False,
    )
    assert rv.status_code == 302


def test_admin_edit_missing_person_redirects(admin_client):
    rv = admin_client.get("/admin/persons/999999999/edit", follow_redirects=False)
    assert rv.status_code == 302
    assert "persons" in rv.headers.get("Location", "").lower()
