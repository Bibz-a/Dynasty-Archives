"""Stored procedures and analytical views."""
from __future__ import annotations

import uuid

import pytest

from app.db import execute_query


def test_vw_reign_durations_non_negative():
    bad = execute_query(
        "SELECT COUNT(*) FROM vw_reign_durations WHERE reign_days < 0"
    )
    assert int(bad[0][0]) == 0


def test_sp_add_ruler_creates_person_and_reign(any_dynasty_id: int):
    suffix = uuid.uuid4().hex[:8]
    name = f"PyTest SP Ruler {suffix}"
    execute_query(
        """
        CALL sp_add_ruler(%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            name,
            "1000-01-01",
            "1050-01-01",
            "pytest bio",
            any_dynasty_id,
            "Emperor",
            "Test City",
            "1010-01-01",
            "1040-01-01",
        ),
    )
    try:
        prow = execute_query(
            "SELECT person_id FROM Person WHERE full_name = %s AND dynasty_id = %s",
            (name, any_dynasty_id),
        )
        assert prow
        pid = int(prow[0][0])
        rrow = execute_query(
            "SELECT reign_id FROM Reign WHERE person_id = %s", (pid,)
        )
        assert rrow
    finally:
        execute_query("DELETE FROM Person WHERE full_name = %s AND dynasty_id = %s", (name, any_dynasty_id))


def test_sp_record_succession_inserts_row(any_dynasty_id: int):
    """Uses disposable Person rows so sp_record_succession can adjust open reigns safely."""
    suffix = uuid.uuid4().hex[:8]
    execute_query(
        """
        INSERT INTO Person (full_name, dynasty_id, birth_date, death_date)
        VALUES (%s, %s, '1150-01-01', '1200-01-01'),
               (%s, %s, '1155-01-01', '1210-01-01')
        """,
        (f"PyPred {suffix}", any_dynasty_id, f"PySucc {suffix}", any_dynasty_id),
    )
    pred = int(
        execute_query(
            "SELECT person_id FROM Person WHERE full_name = %s",
            (f"PyPred {suffix}",),
        )[0][0]
    )
    succ = int(
        execute_query(
            "SELECT person_id FROM Person WHERE full_name = %s",
            (f"PySucc {suffix}",),
        )[0][0]
    )
    execute_query(
        """
        INSERT INTO Reign (person_id, title, start_date, end_date)
        VALUES (%s, 'Test', '1180-01-01', NULL)
        """,
        (pred,),
    )
    notes = f"pytest succession {suffix}"
    try:
        execute_query(
            """
            CALL sp_record_succession(%s, %s, NULL, 'normal'::succession_type, %s, %s)
            """,
            (pred, succ, 1195, notes),
        )
        chk = execute_query(
            """
            SELECT succession_id FROM Succession
            WHERE predecessor_id = %s AND successor_id = %s AND notes = %s
            """,
            (pred, succ, notes),
        )
        assert chk
    finally:
        execute_query(
            "DELETE FROM Succession WHERE predecessor_id = %s OR successor_id = %s",
            (pred, succ),
        )
        execute_query("DELETE FROM Reign WHERE person_id IN (%s, %s)", (pred, succ))
        execute_query("DELETE FROM Person WHERE person_id IN (%s, %s)", (pred, succ))
