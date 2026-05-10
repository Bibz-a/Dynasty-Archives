"""Broad smoke: public 200s + one full dynasty CRUD cycle + person+reign lifecycle."""
from __future__ import annotations

import uuid

from app.db import execute_query

PUBLIC_PATHS = [
    "/",
    "/rulers",
    "/dynasties",
    "/events",
    "/timeline",
    "/territories",
    "/wars",
    "/stats",
    "/search",
]


def test_all_public_routes_200_single_pass(client):
    for p in PUBLIC_PATHS:
        assert client.get(p).status_code == 200, p


def test_full_dynasty_cycle_and_person_reign(admin_client):
    suffix = uuid.uuid4().hex[:8]
    name = f"Smoke Dynasty {suffix}"
    admin_client.post(
        "/admin/dynasties/add",
        data={"name": name, "start_year": "800", "end_year": "900"},
    )
    rows = execute_query("SELECT dynasty_id FROM Dynasty WHERE name = %s", (name,))
    assert rows
    did = int(rows[0][0])

    ruler = f"Smoke Ruler {suffix}"
    admin_client.post(
        "/admin/persons/add",
        data={
            "full_name": ruler,
            "dynasty_id": str(did),
            "title": "Khan",
            "start_date": "0850-01-01",
            "end_date": "0880-01-01",
        },
    )
    pid_row = execute_query(
        "SELECT person_id FROM Person WHERE full_name = %s", (ruler,)
    )
    assert pid_row
    pid = int(pid_row[0][0])
    assert execute_query("SELECT 1 FROM Reign WHERE person_id = %s", (pid,))

    admin_client.post(
        f"/admin/dynasties/{did}/edit",
        data={"name": name + " X", "start_year": "801", "end_year": "901"},
    )
    assert (
        execute_query("SELECT name FROM Dynasty WHERE dynasty_id = %s", (did,))[0][0]
        == name + " X"
    )

    admin_client.post(f"/admin/persons/{pid}/delete", data={})
    admin_client.post(f"/admin/dynasties/{did}/delete", data={})
    assert not execute_query("SELECT 1 FROM Dynasty WHERE dynasty_id = %s", (did,))
