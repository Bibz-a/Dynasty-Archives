from __future__ import annotations

import re
from typing import Any, Iterable

import psycopg2
from flask import g, has_request_context
from psycopg2 import Error as PsycopgError

from config import Config


class DatabaseError(RuntimeError):
    pass


def _format_query_preview(query: str, params: Iterable[Any] | None) -> str:
    """Render a compact SQL preview with bound parameter values."""
    compact = re.sub(r"\s+", " ", (query or "").strip())
    if not params:
        return compact

    values = list(params)
    parts = compact.split("%s")
    if len(parts) == 1:
        return compact

    out: list[str] = [parts[0]]
    for idx, part in enumerate(parts[1:]):
        if idx < len(values):
            value = values[idx]
            if value is None:
                rendered = "NULL"
            elif isinstance(value, str):
                rendered = "'" + value.replace("'", "''") + "'"
            else:
                rendered = str(value)
            out.append(rendered)
        else:
            out.append("%s")
        out.append(part)

    preview = "".join(out)
    return preview if len(preview) <= 420 else (preview[:417] + "...")


def get_connection():
    try:
        return psycopg2.connect(
            host=Config.DB_HOST,
            dbname=Config.DB_NAME,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
        )
    except PsycopgError as e:
        raise DatabaseError(
            "Failed to connect to PostgreSQL. Check DB_HOST/DB_NAME/DB_USER/DB_PASSWORD."
        ) from e
    except Exception as e:
        raise DatabaseError("Unexpected error while connecting to PostgreSQL.") from e


def execute_query(query: str, params: Iterable[Any] | None = None) -> list[tuple[Any, ...]]:
    """
    Opens a connection, runs a query, fetches all results, closes connection, returns results.

    Notes:
    - Intended for SELECT-like queries that return rows.
    - For INSERT/UPDATE/DELETE, results will usually be an empty list unless you use RETURNING.
    """
    conn = None
    cur = None
    try:
        if has_request_context():
            preview = _format_query_preview(query, params)
            g.last_query = preview
            if not hasattr(g, "query_log"):
                g.query_log = []
            g.query_log.append(
                {
                    "sql": query,
                    "params": list(params) if params is not None else None,
                    "preview": preview,
                }
            )
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall() if cur.description is not None else []
        conn.commit()
        return rows
    except PsycopgError as e:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        raise DatabaseError(f"Database query failed: {e.pgerror or str(e)}") from e
    except Exception as e:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        raise DatabaseError(
            f"Unexpected error while executing database query. Underlying error: {type(e).__name__}: {e}"
        ) from e
    finally:
        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def log_audit(
    table: str,
    operation: str,
    record_id: int | None,
    user: str | None,
    details: str | None,
) -> None:
    """Insert a structured audit row into Audit_Log."""
    execute_query(
        """
        INSERT INTO Audit_Log (table_name, operation, record_id, performed_by, details)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (table, operation, record_id, user, details),
    )