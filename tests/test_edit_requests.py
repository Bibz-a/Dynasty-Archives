"""Viewer suggestions → admin queue → approve / decline."""
from __future__ import annotations

import uuid

import pytest

from app.db import execute_query


@pytest.fixture()
def suffix():
    return uuid.uuid4().hex[:8]


def test_edit_request_flow_approve_and_decline(
    viewer_client, admin_client, any_person_id: int, any_dynasty_id: int, suffix: str
):
    person_rows = execute_query(
        "SELECT full_name FROM Person WHERE person_id = %s", (any_person_id,)
    )
    if not person_rows:
        pytest.skip("Missing person.")
    original_name = str(person_rows[0][0])
    new_name = f"{original_name} [pytest {suffix}]"

    viewer_client.post(
        f"/rulers/{any_person_id}/suggest",
        data={
            "field_name": "full_name",
            "new_value": new_name,
            "reason": "pytest",
        },
        follow_redirects=False,
    )
    req_row = execute_query(
        """
        SELECT request_id FROM Edit_Request
        WHERE entity_type = 'person' AND entity_id = %s AND new_value = %s AND status = 'pending'
        ORDER BY request_id DESC LIMIT 1
        """,
        (any_person_id, new_name),
    )
    assert req_row
    rid = int(req_row[0][0])

    rv = admin_client.get("/admin/edit-requests")
    assert rv.status_code == 200
    assert str(new_name).encode() in rv.data or str(rid).encode() in rv.data

    admin_client.post(f"/admin/edit-requests/{rid}/approve", data={})
    updated = execute_query(
        "SELECT full_name FROM Person WHERE person_id = %s", (any_person_id,)
    )
    assert updated[0][0] == new_name
    execute_query(
        "UPDATE Person SET full_name = %s WHERE person_id = %s",
        (original_name, any_person_id),
    )
    execute_query("DELETE FROM Edit_Request WHERE request_id = %s", (rid,))

    dynasty_rows = execute_query(
        "SELECT name FROM Dynasty WHERE dynasty_id = %s", (any_dynasty_id,)
    )
    orig_d_name = str(dynasty_rows[0][0])
    sug_name = f"{orig_d_name} [pytest d {suffix}]"
    viewer_client.post(
        f"/dynasties/{any_dynasty_id}/suggest",
        data={
            "field_name": "name",
            "new_value": sug_name,
            "reason": "pytest decline",
        },
    )
    dreq = execute_query(
        """
        SELECT request_id FROM Edit_Request
        WHERE entity_type = 'dynasty' AND entity_id = %s AND status = 'pending'
        ORDER BY request_id DESC LIMIT 1
        """,
        (any_dynasty_id,),
    )
    assert dreq
    drid = int(dreq[0][0])
    admin_client.post(f"/admin/edit-requests/{drid}/decline", data={})
    st = execute_query(
        "SELECT status FROM Edit_Request WHERE request_id = %s", (drid,)
    )
    assert st[0][0] == "declined"
    still = execute_query(
        "SELECT name FROM Dynasty WHERE dynasty_id = %s", (any_dynasty_id,)
    )
    assert still[0][0] == orig_d_name
    execute_query("DELETE FROM Edit_Request WHERE request_id = %s", (drid,))
