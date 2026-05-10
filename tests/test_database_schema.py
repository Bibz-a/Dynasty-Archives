"""Schema: tables, views, indexes, triggers, check constraints."""
from __future__ import annotations

import pytest

from app.db import DatabaseError, execute_query

EXPECTED_TABLES = {
    "dynasty",
    "person",
    "reign",
    "event",
    "territory",
    "user_account",
    "succession",
    "parent_child",
    "person_event",
    "dynasty_territory",
    "audit_log",
    "edit_request",
    "relation",
    "event_relation",
}

EXPECTED_VIEWS = {
    "vw_reign_durations",
    "vw_succession_chain",
    "vw_wars_and_battles",
    "vw_territory_timeline",
}

EXPECTED_INDEXES = {
    "idx_person_dynasty",
    "idx_reign_person",
    "idx_succession_pred",
    "idx_succession_succ",
    "idx_event_type",
    "idx_event_date",
    "idx_person_event",
    "idx_dynasty_terr",
}

EXPECTED_TRIGGERS = {
    "trg_dynasty_updated",
    "trg_person_updated",
    "trg_person_deleted",
    "trg_dynasty_deleted",
    "trg_reign_dates_check",
}


def test_all_tables_exist():
    rows = execute_query(
        """
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public' AND tablename NOT LIKE 'pg_%'
        """
    )
    found = {str(r[0]).lower() for r in rows}
    missing = EXPECTED_TABLES - found
    assert not missing, f"Missing tables: {missing}"


def test_all_views_exist():
    rows = execute_query(
        """
        SELECT table_name FROM information_schema.views
        WHERE table_schema = 'public'
        """
    )
    found = {str(r[0]).lower() for r in rows}
    missing = EXPECTED_VIEWS - found
    assert not missing, f"Missing views: {missing}"


def test_indexes_exist():
    rows = execute_query(
        """
        SELECT indexname FROM pg_indexes
        WHERE schemaname = 'public'
        """
    )
    found = {str(r[0]).lower() for r in rows}
    missing = {i.lower() for i in EXPECTED_INDEXES} - found
    assert not missing, f"Missing indexes: {missing}"


def test_triggers_exist():
    rows = execute_query(
        """
        SELECT t.tgname
        FROM pg_trigger t
        JOIN pg_class c ON c.oid = t.tgrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE NOT t.tgisinternal AND n.nspname = 'public'
        """
    )
    found = {str(r[0]).lower() for r in rows}
    missing = {t.lower() for t in EXPECTED_TRIGGERS} - found
    assert not missing, f"Missing triggers: {missing}"


def test_check_dynasty_years_rejected():
    with pytest.raises(DatabaseError):
        execute_query(
            "INSERT INTO Dynasty (name, start_year, end_year) VALUES (%s, %s, %s)",
            ("__pytest_bad_dyn__", 2000, 1990),
        )


def test_check_person_dates_rejected(any_dynasty_id: int):
    with pytest.raises(DatabaseError):
        execute_query(
            """
            INSERT INTO Person (full_name, birth_date, death_date, dynasty_id)
            VALUES (%s, %s, %s, %s)
            """,
            ("__pytest_bad_person__", "2000-01-01", "1990-01-01", any_dynasty_id),
        )


def test_check_parent_child_no_self(any_person_id: int):
    with pytest.raises(DatabaseError):
        execute_query(
            "INSERT INTO Parent_Child (parent_id, child_id) VALUES (%s, %s)",
            (any_person_id, any_person_id),
        )


def test_check_succession_different_people(any_person_id: int):
    with pytest.raises(DatabaseError):
        execute_query(
            """
            INSERT INTO Succession (predecessor_id, successor_id, type)
            VALUES (%s, %s, 'normal')
            """,
            (any_person_id, any_person_id),
        )
