from __future__ import annotations

import os
import re
import base64
import subprocess
from collections import defaultdict
from datetime import date
from datetime import datetime
from functools import wraps
from urllib.parse import urlparse

import psycopg2
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user
from flask_login import login_required
from werkzeug.security import check_password_hash

from app.db import DatabaseError, execute_query, log_audit
from app.supabase_client import SUPABASE_BACKUP_BUCKET, get_supabase_client
from app.uploads import UploadError, save_image_local_path

admin_bp = Blueprint("admin", __name__)


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not getattr(current_user, "is_authenticated", False) or getattr(current_user, "role", None) != "admin":
            flash("Admin access required.", "error")
            return redirect(url_for("auth.login"))
        return view_func(*args, **kwargs)

    return wrapper


def _parse_date(value: str | None) -> date | None:
    value = (value or "").strip()
    if not value:
        return None
    # HTML date input uses YYYY-MM-DD
    return date.fromisoformat(value)


def _validate_max_length(value: str | None, limit: int, label: str):
    if value and len(value) > limit:
        raise ValueError(f"{label} must be {limit} characters or fewer.")


def _normalize_local_image_path(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    if raw.startswith(("http://", "https://", "data:")):
        return raw
    if raw.startswith("/images/"):
        return raw
    if raw.startswith("images/"):
        return "/" + raw
    return f"/images/{raw.lstrip('/')}"


def _parse_int_list(values: list[str]) -> list[int]:
    parsed: list[int] = []
    seen: set[int] = set()
    for raw in values:
        try:
            num = int((raw or "").strip())
        except (TypeError, ValueError):
            continue
        if num > 0 and num not in seen:
            seen.add(num)
            parsed.append(num)
    return parsed


def _sync_person_links(
    person_id: int,
    spouse_ids: list[int],
    child_ids: list[int],
    parent_ids: list[int],
    predecessor_ids: list[int],
    successor_ids: list[int],
    event_ids: list[int],
) -> None:
    """Replace optional relationship/event links for a person."""
    execute_query(
        "DELETE FROM Relation WHERE relation_type = 'spouse' AND (person_a_id = %s OR person_b_id = %s)",
        (person_id, person_id),
    )
    execute_query("DELETE FROM Parent_Child WHERE parent_id = %s OR child_id = %s", (person_id, person_id))
    execute_query("DELETE FROM Succession WHERE predecessor_id = %s OR successor_id = %s", (person_id, person_id))
    execute_query("DELETE FROM Person_Event WHERE person_id = %s", (person_id,))

    for spouse_id in spouse_ids:
        if spouse_id == person_id:
            continue
        execute_query(
            """
            INSERT INTO Relation (person_a_id, person_b_id, relation_type)
            VALUES (%s, %s, 'spouse')
            """,
            (person_id, spouse_id),
        )

    for child_id in child_ids:
        if child_id == person_id:
            continue
        execute_query(
            """
            INSERT INTO Parent_Child (parent_id, child_id)
            VALUES (%s, %s)
            ON CONFLICT (parent_id, child_id) DO NOTHING
            """,
            (person_id, child_id),
        )
    for parent_id in parent_ids:
        if parent_id == person_id:
            continue
        execute_query(
            """
            INSERT INTO Parent_Child (parent_id, child_id)
            VALUES (%s, %s)
            ON CONFLICT (parent_id, child_id) DO NOTHING
            """,
            (parent_id, person_id),
        )

    for predecessor_id in predecessor_ids:
        if predecessor_id == person_id:
            continue
        execute_query(
            """
            INSERT INTO Succession (predecessor_id, successor_id, type)
            VALUES (%s, %s, 'normal')
            """,
            (predecessor_id, person_id),
        )
    for successor_id in successor_ids:
        if successor_id == person_id:
            continue
        execute_query(
            """
            INSERT INTO Succession (predecessor_id, successor_id, type)
            VALUES (%s, %s, 'normal')
            """,
            (person_id, successor_id),
        )

    for event_id in event_ids:
        execute_query(
            """
            INSERT INTO Person_Event (person_id, event_id, role)
            VALUES (%s, %s, NULL)
            ON CONFLICT (person_id, event_id) DO NOTHING
            """,
            (person_id, event_id),
        )


def _sync_dynasty_links(
    dynasty_id: int,
    ruler_ids: list[int],
    territory_ids: list[int],
    event_ids: list[int],
) -> None:
    """Sync optional dynasty links for rulers, territories, and events."""
    if ruler_ids:
        execute_query(
            "UPDATE Person SET dynasty_id = %s WHERE person_id = ANY(%s)",
            (dynasty_id, ruler_ids),
        )
    execute_query("DELETE FROM Dynasty_Territory WHERE dynasty_id = %s", (dynasty_id,))
    for territory_id in territory_ids:
        execute_query(
            """
            INSERT INTO Dynasty_Territory (dynasty_id, territory_id)
            VALUES (%s, %s)
            ON CONFLICT (dynasty_id, territory_id) DO NOTHING
            """,
            (dynasty_id, territory_id),
        )
    execute_query("UPDATE Event SET dynasty_id = NULL WHERE dynasty_id = %s", (dynasty_id,))
    if event_ids:
        execute_query(
            "UPDATE Event SET dynasty_id = %s WHERE event_id = ANY(%s)",
            (dynasty_id, event_ids),
        )


def _ensure_event_relation_table() -> None:
    execute_query(
        """
        CREATE TABLE IF NOT EXISTS Event_Relation (
            event_id INT NOT NULL REFERENCES Event(event_id) ON DELETE CASCADE,
            related_event_id INT NOT NULL REFERENCES Event(event_id) ON DELETE CASCADE,
            relation_type VARCHAR(50) NOT NULL DEFAULT 'related_battle',
            PRIMARY KEY (event_id, related_event_id),
            CONSTRAINT chk_event_relation_diff CHECK (event_id <> related_event_id)
        )
        """
    )


def _sync_event_links(event_id: int, participant_ids: list[int], related_battle_ids: list[int]) -> None:
    """Sync optional war links for participants and explicitly related battles."""
    _ensure_event_relation_table()
    execute_query("DELETE FROM Person_Event WHERE event_id = %s", (event_id,))
    for person_id in participant_ids:
        execute_query(
            """
            INSERT INTO Person_Event (person_id, event_id, role)
            VALUES (%s, %s, NULL)
            ON CONFLICT (person_id, event_id) DO NOTHING
            """,
            (person_id, event_id),
        )

    execute_query("DELETE FROM Event_Relation WHERE event_id = %s OR related_event_id = %s", (event_id, event_id))
    for related_id in related_battle_ids:
        if related_id == event_id:
            continue
        execute_query(
            """
            INSERT INTO Event_Relation (event_id, related_event_id, relation_type)
            VALUES (%s, %s, 'related_battle')
            ON CONFLICT (event_id, related_event_id) DO NOTHING
            """,
            (event_id, related_id),
        )
        execute_query(
            """
            INSERT INTO Event_Relation (event_id, related_event_id, relation_type)
            VALUES (%s, %s, 'related_battle')
            ON CONFLICT (event_id, related_event_id) DO NOTHING
            """,
            (related_id, event_id),
        )


@admin_bp.route("/")
@login_required
@admin_required
def dashboard():
    dynasties_count = execute_query("SELECT COUNT(*) FROM Dynasty")[0][0]
    persons_count = execute_query("SELECT COUNT(*) FROM Person")[0][0]
    events_count = execute_query("SELECT COUNT(*) FROM Event")[0][0]
    territories_count = execute_query("SELECT COUNT(*) FROM Territory")[0][0]
    last_backup_rows = execute_query(
        """
        SELECT details, performed_at::text
        FROM Audit_Log
        WHERE table_name = 'DATABASE'
        ORDER BY performed_at DESC
        LIMIT 1
        """
    )
    last_backup = last_backup_rows[0] if last_backup_rows else None
    recent_activity = execute_query(
        """
        SELECT table_name, operation, record_id, performed_by, performed_at, details
        FROM Audit_Log
        WHERE table_name != 'DATABASE'
        ORDER BY performed_at DESC
        LIMIT 10
        """
    )
    recent_backups = execute_query(
        """
        SELECT performed_at, performed_by, details
        FROM Audit_Log
        WHERE table_name = 'DATABASE' AND operation = 'BACKUP'
        ORDER BY performed_at DESC
        LIMIT 10
        """
    )
    return render_template(
        "admin/dashboard.html",
        counts={
            "dynasties": int(dynasties_count),
            "persons": int(persons_count),
            "events": int(events_count),
            "territories": int(territories_count),
        },
        last_backup=last_backup,
        recent_activity=recent_activity,
        recent_backups=recent_backups,
        pending_edit_count=int(
            execute_query("SELECT COUNT(*) FROM Edit_Request WHERE status = 'pending'")[0][0]
        ),
    )


# -----------------------------
# Dynasty CRUD
# -----------------------------


@admin_bp.route("/dynasties")
@login_required
@admin_required
def dynasties_list():
    rows = execute_query(
        """
        SELECT dynasty_id, name, start_year, end_year, description
        FROM Dynasty
        ORDER BY start_year NULLS LAST, name
        """
    )
    return render_template("admin/dynasties.html", dynasties=rows)


@admin_bp.route("/dynasties/add", methods=["GET", "POST"])
@login_required
@admin_required
def dynasty_add():
    people = execute_query("SELECT person_id, full_name FROM Person ORDER BY full_name")
    territories = execute_query("SELECT territory_id, name FROM Territory ORDER BY name")
    events = execute_query("SELECT event_id, name FROM Event ORDER BY event_date NULLS LAST, name")
    if request.method == "GET":
        return render_template(
            "admin/dynasty_form.html",
            mode="add",
            dynasty=None,
            people=people,
            territories=territories,
            events=events,
            selected_ruler_ids=[],
            selected_territory_ids=[],
            selected_event_ids=[],
        )

    name = (request.form.get("name") or "").strip()
    start_year = (request.form.get("start_year") or "").strip() or None
    end_year = (request.form.get("end_year") or "").strip() or None
    description = (request.form.get("description") or "").strip() or None
    image_url = _normalize_local_image_path(request.form.get("image_url"))
    ruler_ids = _parse_int_list(request.form.getlist("ruler_ids"))
    territory_ids = _parse_int_list(request.form.getlist("territory_ids"))
    event_ids = _parse_int_list(request.form.getlist("event_ids"))
    image_file = request.files.get("image_file")
    if image_file and getattr(image_file, "filename", ""):
        try:
            image_url = save_image_local_path(image_file, "dynasties")
        except UploadError as e:
            flash(f"Image upload failed: {e}", "error")
            return redirect(url_for("admin.dynasty_add"))

    if not name:
        flash("Name is required.", "error")
        return redirect(url_for("admin.dynasty_add"))
    try:
        _validate_max_length(name, 150, "Name")
        _validate_max_length(description, 5000, "Description")
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("admin.dynasty_add"))

    try:
        inserted = execute_query(
            """
            INSERT INTO Dynasty (name, start_year, end_year, description, image_url)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING dynasty_id
            """,
            (
                name,
                int(start_year) if start_year is not None else None,
                int(end_year) if end_year is not None else None,
                description,
                image_url,
            ),
        )
        dynasty_id_new = int(inserted[0][0]) if inserted else None
        if dynasty_id_new is not None:
            _sync_dynasty_links(dynasty_id_new, ruler_ids, territory_ids, event_ids)
        log_audit("Dynasty", "INSERT", dynasty_id_new, current_user.username, f"Created dynasty '{name}'")
    except (ValueError, DatabaseError) as e:
        flash(f"Failed to add dynasty: {e}", "error")
        return redirect(url_for("admin.dynasty_add"))

    flash("Dynasty added successfully.", "success")
    return redirect(url_for("admin.dynasties_list"))


@admin_bp.route("/dynasties/<int:dynasty_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def dynasty_edit(dynasty_id: int):
    people = execute_query("SELECT person_id, full_name FROM Person ORDER BY full_name")
    territories = execute_query("SELECT territory_id, name FROM Territory ORDER BY name")
    events = execute_query("SELECT event_id, name FROM Event ORDER BY event_date NULLS LAST, name")
    rows = execute_query(
        """
        SELECT dynasty_id, name, start_year, end_year, description, image_url
        FROM Dynasty
        WHERE dynasty_id = %s
        """,
        (dynasty_id,),
    )
    if not rows:
        flash("Dynasty not found.", "error")
        return redirect(url_for("admin.dynasties_list"))
    dynasty = rows[0]
    selected_ruler_ids = [int(r[0]) for r in execute_query("SELECT person_id FROM Person WHERE dynasty_id = %s", (dynasty_id,))]
    selected_territory_ids = [int(r[0]) for r in execute_query("SELECT territory_id FROM Dynasty_Territory WHERE dynasty_id = %s", (dynasty_id,))]
    selected_event_ids = [int(r[0]) for r in execute_query("SELECT event_id FROM Event WHERE dynasty_id = %s", (dynasty_id,))]

    if request.method == "GET":
        return render_template(
            "admin/dynasty_form.html",
            mode="edit",
            dynasty=dynasty,
            people=people,
            territories=territories,
            events=events,
            selected_ruler_ids=selected_ruler_ids,
            selected_territory_ids=selected_territory_ids,
            selected_event_ids=selected_event_ids,
        )

    name = (request.form.get("name") or "").strip()
    start_year = (request.form.get("start_year") or "").strip() or None
    end_year = (request.form.get("end_year") or "").strip() or None
    description = (request.form.get("description") or "").strip() or None
    image_url = _normalize_local_image_path(request.form.get("image_url"))
    ruler_ids = _parse_int_list(request.form.getlist("ruler_ids"))
    territory_ids = _parse_int_list(request.form.getlist("territory_ids"))
    event_ids = _parse_int_list(request.form.getlist("event_ids"))
    image_file = request.files.get("image_file")
    if image_file and getattr(image_file, "filename", ""):
        try:
            image_url = save_image_local_path(image_file, "dynasties")
        except UploadError as e:
            flash(f"Image upload failed: {e}", "error")
            return redirect(url_for("admin.dynasty_edit", dynasty_id=dynasty_id))

    if not name:
        flash("Name is required.", "error")
        return redirect(url_for("admin.dynasty_edit", dynasty_id=dynasty_id))
    try:
        _validate_max_length(name, 150, "Name")
        _validate_max_length(description, 5000, "Description")
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("admin.dynasty_edit", dynasty_id=dynasty_id))

    try:
        execute_query(
            """
            UPDATE Dynasty
            SET name = %s, start_year = %s, end_year = %s, description = %s, image_url = %s
            WHERE dynasty_id = %s
            """,
            (
                name,
                int(start_year) if start_year is not None else None,
                int(end_year) if end_year is not None else None,
                description,
                image_url,
                dynasty_id,
            ),
        )
        _sync_dynasty_links(dynasty_id, ruler_ids, territory_ids, event_ids)
        log_audit("Dynasty", "UPDATE", dynasty_id, current_user.username, f"Updated dynasty '{name}'")
    except (ValueError, DatabaseError) as e:
        flash(f"Failed to update dynasty: {e}", "error")
        return redirect(url_for("admin.dynasty_edit", dynasty_id=dynasty_id))

    flash("Dynasty updated successfully.", "success")
    return redirect(url_for("admin.dynasties_list"))


@admin_bp.route("/dynasties/<int:dynasty_id>/delete", methods=["POST"])
@login_required
@admin_required
def dynasty_delete(dynasty_id: int):
    try:
        execute_query("DELETE FROM Dynasty WHERE dynasty_id = %s", (dynasty_id,))
        log_audit("Dynasty", "DELETE", dynasty_id, current_user.username, "Deleted dynasty")
    except DatabaseError as e:
        flash(f"Failed to delete dynasty: {e}", "error")
        return redirect(url_for("admin.dynasties_list"))

    flash("Dynasty deleted.", "success")
    return redirect(url_for("admin.dynasties_list"))


# -----------------------------
# Person (Ruler) CRUD
# -----------------------------


@admin_bp.route("/persons")
@login_required
@admin_required
def persons_list():
    rows = execute_query(
        """
        SELECT p.person_id, p.full_name, d.name, p.birth_date::text, p.death_date::text
        FROM Person p
        JOIN Dynasty d ON d.dynasty_id = p.dynasty_id
        ORDER BY p.full_name
        """
    )
    return render_template("admin/persons.html", persons=rows)


@admin_bp.route("/persons/add", methods=["GET", "POST"])
@login_required
@admin_required
def person_add():
    dynasties = execute_query("SELECT dynasty_id, name FROM Dynasty ORDER BY name")
    people = execute_query("SELECT person_id, full_name FROM Person ORDER BY full_name")
    events = execute_query("SELECT event_id, name FROM Event ORDER BY event_date NULLS LAST, name")

    if request.method == "GET":
        return render_template(
            "admin/person_form.html",
            mode="add",
            person=None,
            dynasties=dynasties,
            people=people,
            events=events,
            selected_spouse_ids=[],
            selected_child_ids=[],
            selected_parent_ids=[],
            selected_predecessor_ids=[],
            selected_successor_ids=[],
            selected_event_ids=[],
        )

    full_name = (request.form.get("full_name") or "").strip()
    dynasty_id = (request.form.get("dynasty_id") or "").strip()
    birth_date = _parse_date(request.form.get("birth_date"))
    death_date = _parse_date(request.form.get("death_date"))
    biography = (request.form.get("biography") or "").strip() or None
    image_url = _normalize_local_image_path(request.form.get("image_url"))
    image_file = request.files.get("image_file")
    if image_file and getattr(image_file, "filename", ""):
        try:
            image_url = save_image_local_path(image_file, "persons")
        except UploadError as e:
            flash(f"Image upload failed: {e}", "error")
            return redirect(url_for("admin.person_add"))

    # Optional first reign fields
    title = (request.form.get("title") or "").strip() or None
    capital = (request.form.get("capital") or "").strip() or None
    reign_start = _parse_date(request.form.get("start_date"))
    reign_end = _parse_date(request.form.get("end_date"))
    spouse_ids = _parse_int_list(request.form.getlist("spouse_ids"))
    child_ids = _parse_int_list(request.form.getlist("child_ids"))
    parent_ids = _parse_int_list(request.form.getlist("parent_ids"))
    predecessor_ids = _parse_int_list(request.form.getlist("predecessor_ids"))
    successor_ids = _parse_int_list(request.form.getlist("successor_ids"))
    event_ids = _parse_int_list(request.form.getlist("event_ids"))

    if not full_name:
        flash("Full name is required.", "error")
        return redirect(url_for("admin.person_add"))
    if not dynasty_id:
        flash("Dynasty is required.", "error")
        return redirect(url_for("admin.person_add"))

    try:
        did = int(dynasty_id)
    except ValueError:
        flash("Invalid dynasty selected.", "error")
        return redirect(url_for("admin.person_add"))
    try:
        _validate_max_length(full_name, 200, "Full name")
        _validate_max_length(biography, 5000, "Biography")
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("admin.person_add"))

    try:
        new_person_id: int | None = None
        if title and reign_start:
            # Stored procedure inserts both Person + first Reign.
            execute_query(
                """
                CALL sp_add_ruler(%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    full_name,
                    birth_date,
                    death_date,
                    biography,
                    did,
                    title,
                    capital,
                    reign_start,
                    reign_end,
                ),
            )
            created_person = execute_query(
                """
                SELECT person_id
                FROM Person
                WHERE full_name = %s AND dynasty_id = %s
                ORDER BY person_id DESC
                LIMIT 1
                """,
                (full_name, did),
            )
            new_person_id = int(created_person[0][0]) if created_person else None
            log_audit("Person", "INSERT", new_person_id, current_user.username, f"Created person '{full_name}' via stored procedure")
        else:
            inserted = execute_query(
                """
                INSERT INTO Person (full_name, birth_date, death_date, biography, image_url, dynasty_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING person_id
                """,
                (full_name, birth_date, death_date, biography, image_url, did),
            )
            person_id_new = int(inserted[0][0]) if inserted else None
            new_person_id = person_id_new
            log_audit("Person", "INSERT", person_id_new, current_user.username, f"Created person '{full_name}'")
        if new_person_id is not None:
            _sync_person_links(
                new_person_id,
                spouse_ids,
                child_ids,
                parent_ids,
                predecessor_ids,
                successor_ids,
                event_ids,
            )
    except DatabaseError as e:
        flash(f"Failed to add person: {e}", "error")
        return redirect(url_for("admin.person_add"))

    flash("Person added successfully.", "success")
    return redirect(url_for("admin.persons_list"))


@admin_bp.route("/persons/<int:person_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def person_edit(person_id: int):
    dynasties = execute_query("SELECT dynasty_id, name FROM Dynasty ORDER BY name")
    people = execute_query("SELECT person_id, full_name FROM Person ORDER BY full_name")
    events = execute_query("SELECT event_id, name FROM Event ORDER BY event_date NULLS LAST, name")
    rows = execute_query(
        """
        SELECT person_id, full_name, birth_date::text, death_date::text, biography, image_url, dynasty_id
        FROM Person
        WHERE person_id = %s
        """,
        (person_id,),
    )
    if not rows:
        flash("Person not found.", "error")
        return redirect(url_for("admin.persons_list"))
    person = rows[0]
    selected_spouse_ids = [int(r[0]) for r in execute_query("SELECT CASE WHEN person_a_id = %s THEN person_b_id ELSE person_a_id END FROM Relation WHERE relation_type = 'spouse' AND (person_a_id = %s OR person_b_id = %s)", (person_id, person_id, person_id))]
    selected_child_ids = [int(r[0]) for r in execute_query("SELECT child_id FROM Parent_Child WHERE parent_id = %s", (person_id,))]
    selected_parent_ids = [int(r[0]) for r in execute_query("SELECT parent_id FROM Parent_Child WHERE child_id = %s", (person_id,))]
    selected_predecessor_ids = [int(r[0]) for r in execute_query("SELECT predecessor_id FROM Succession WHERE successor_id = %s", (person_id,))]
    selected_successor_ids = [int(r[0]) for r in execute_query("SELECT successor_id FROM Succession WHERE predecessor_id = %s", (person_id,))]
    selected_event_ids = [int(r[0]) for r in execute_query("SELECT event_id FROM Person_Event WHERE person_id = %s", (person_id,))]

    if request.method == "GET":
        return render_template(
            "admin/person_form.html",
            mode="edit",
            person=person,
            dynasties=dynasties,
            people=people,
            events=events,
            selected_spouse_ids=selected_spouse_ids,
            selected_child_ids=selected_child_ids,
            selected_parent_ids=selected_parent_ids,
            selected_predecessor_ids=selected_predecessor_ids,
            selected_successor_ids=selected_successor_ids,
            selected_event_ids=selected_event_ids,
        )

    full_name = (request.form.get("full_name") or "").strip()
    dynasty_id = (request.form.get("dynasty_id") or "").strip()
    birth_date = _parse_date(request.form.get("birth_date"))
    death_date = _parse_date(request.form.get("death_date"))
    biography = (request.form.get("biography") or "").strip() or None
    image_url = _normalize_local_image_path(request.form.get("image_url"))
    spouse_ids = _parse_int_list(request.form.getlist("spouse_ids"))
    child_ids = _parse_int_list(request.form.getlist("child_ids"))
    parent_ids = _parse_int_list(request.form.getlist("parent_ids"))
    predecessor_ids = _parse_int_list(request.form.getlist("predecessor_ids"))
    successor_ids = _parse_int_list(request.form.getlist("successor_ids"))
    event_ids = _parse_int_list(request.form.getlist("event_ids"))
    image_file = request.files.get("image_file")
    if image_file and getattr(image_file, "filename", ""):
        try:
            image_url = save_image_local_path(image_file, "persons")
        except UploadError as e:
            flash(f"Image upload failed: {e}", "error")
            return redirect(url_for("admin.person_edit", person_id=person_id))

    if not full_name:
        flash("Full name is required.", "error")
        return redirect(url_for("admin.person_edit", person_id=person_id))
    try:
        did = int(dynasty_id)
    except ValueError:
        flash("Invalid dynasty selected.", "error")
        return redirect(url_for("admin.person_edit", person_id=person_id))
    try:
        _validate_max_length(full_name, 200, "Full name")
        _validate_max_length(biography, 5000, "Biography")
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("admin.person_edit", person_id=person_id))

    try:
        execute_query(
            """
            UPDATE Person
            SET full_name = %s,
                birth_date = %s,
                death_date = %s,
                biography = %s,
                image_url = %s,
                dynasty_id = %s
            WHERE person_id = %s
            """,
            (full_name, birth_date, death_date, biography, image_url, did, person_id),
        )
        _sync_person_links(
            person_id,
            spouse_ids,
            child_ids,
            parent_ids,
            predecessor_ids,
            successor_ids,
            event_ids,
        )
        log_audit("Person", "UPDATE", person_id, current_user.username, f"Updated person '{full_name}'")
    except DatabaseError as e:
        flash(f"Failed to update person: {e}", "error")
        return redirect(url_for("admin.person_edit", person_id=person_id))

    flash("Person updated successfully.", "success")
    return redirect(url_for("admin.persons_list"))


@admin_bp.route("/persons/<int:person_id>/delete", methods=["POST"])
@login_required
@admin_required
def person_delete(person_id: int):
    try:
        execute_query("DELETE FROM Person WHERE person_id = %s", (person_id,))
        log_audit("Person", "DELETE", person_id, current_user.username, "Deleted person")
    except DatabaseError as e:
        flash(f"Failed to delete person: {e}", "error")
        return redirect(url_for("admin.persons_list"))

    flash("Person deleted.", "success")
    return redirect(url_for("admin.persons_list"))


# -----------------------------
# Event CRUD
# -----------------------------


@admin_bp.route("/events")
@login_required
@admin_required
def events_list():
    rows = execute_query(
        """
        SELECT e.event_id, e.name, e.type::text, e.event_date::text, e.location, d.name
        FROM Event e
        LEFT JOIN Dynasty d ON d.dynasty_id = e.dynasty_id
        ORDER BY e.event_date NULLS LAST, e.name
        """
    )
    return render_template("admin/events.html", events=rows)


@admin_bp.route("/events/add", methods=["GET", "POST"])
@login_required
@admin_required
def event_add():
    dynasties = execute_query("SELECT dynasty_id, name FROM Dynasty ORDER BY name")
    people = execute_query("SELECT person_id, full_name FROM Person ORDER BY full_name")
    battle_events = execute_query("SELECT event_id, name FROM Event WHERE type = 'battle' ORDER BY event_date NULLS LAST, name")
    types = [
        "war",
        "battle",
        "treaty",
        "coronation",
        "death",
        "birth",
        "political",
        "natural_disaster",
        "other",
    ]

    if request.method == "GET":
        return render_template(
            "admin/event_form.html",
            mode="add",
            event=None,
            dynasties=dynasties,
            types=types,
            people=people,
            battle_events=battle_events,
            selected_participant_ids=[],
            selected_related_battle_ids=[],
        )

    name = (request.form.get("name") or "").strip()
    type_ = (request.form.get("type") or "").strip()
    event_date = _parse_date(request.form.get("event_date"))
    end_date = _parse_date(request.form.get("end_date"))
    location = (request.form.get("location") or "").strip() or None
    description = (request.form.get("description") or "").strip() or None
    dynasty_id = (request.form.get("dynasty_id") or "").strip() or None
    image_url = _normalize_local_image_path(request.form.get("image_url"))
    participant_ids = _parse_int_list(request.form.getlist("participant_ids"))
    related_battle_ids = _parse_int_list(request.form.getlist("related_battle_ids"))

    image_file = request.files.get("image_file")
    if image_file and getattr(image_file, "filename", ""):
        try:
            image_url = save_image_local_path(image_file, "events")
        except UploadError as e:
            flash(f"Image upload failed: {e}", "error")
            return redirect(url_for("admin.event_add"))

    if not name:
        flash("Name is required.", "error")
        return redirect(url_for("admin.event_add"))
    if not type_:
        flash("Type is required.", "error")
        return redirect(url_for("admin.event_add"))
    try:
        _validate_max_length(name, 150, "Name")
        _validate_max_length(description, 5000, "Description")
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("admin.event_add"))

    did = None
    if dynasty_id:
        try:
            did = int(dynasty_id)
        except ValueError:
            flash("Invalid dynasty selected.", "error")
            return redirect(url_for("admin.event_add"))

    try:
        inserted = execute_query(
            """
            INSERT INTO Event (name, type, event_date, end_date, location, description, image_url, dynasty_id)
            VALUES (%s, %s::event_type, %s, %s, %s, %s, %s, %s)
            RETURNING event_id
            """,
            (name, type_, event_date, end_date, location, description, image_url, did),
        )
        event_id_new = int(inserted[0][0]) if inserted else None
        if event_id_new is not None:
            _sync_event_links(event_id_new, participant_ids, related_battle_ids)
        log_audit("Event", "INSERT", event_id_new, current_user.username, f"Created event '{name}'")
    except DatabaseError as e:
        flash(f"Failed to add event: {e}", "error")
        return redirect(url_for("admin.event_add"))

    flash("Event added successfully.", "success")
    return redirect(url_for("admin.events_list"))


@admin_bp.route("/events/<int:event_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def event_edit(event_id: int):
    dynasties = execute_query("SELECT dynasty_id, name FROM Dynasty ORDER BY name")
    people = execute_query("SELECT person_id, full_name FROM Person ORDER BY full_name")
    battle_events = execute_query("SELECT event_id, name FROM Event WHERE type = 'battle' AND event_id <> %s ORDER BY event_date NULLS LAST, name", (event_id,))
    types = [
        "war",
        "battle",
        "treaty",
        "coronation",
        "death",
        "birth",
        "political",
        "natural_disaster",
        "other",
    ]
    rows = execute_query(
        """
        SELECT event_id, name, type::text, event_date::text, end_date::text, location, description, image_url, dynasty_id
        FROM Event
        WHERE event_id = %s
        """,
        (event_id,),
    )
    if not rows:
        flash("Event not found.", "error")
        return redirect(url_for("admin.events_list"))
    event = rows[0]
    selected_participant_ids = [int(r[0]) for r in execute_query("SELECT person_id FROM Person_Event WHERE event_id = %s", (event_id,))]
    try:
        _ensure_event_relation_table()
        selected_related_battle_ids = [int(r[0]) for r in execute_query("SELECT related_event_id FROM Event_Relation WHERE event_id = %s AND relation_type = 'related_battle'", (event_id,))]
    except Exception:
        selected_related_battle_ids = []

    if request.method == "GET":
        return render_template(
            "admin/event_form.html",
            mode="edit",
            event=event,
            dynasties=dynasties,
            types=types,
            people=people,
            battle_events=battle_events,
            selected_participant_ids=selected_participant_ids,
            selected_related_battle_ids=selected_related_battle_ids,
        )

    name = (request.form.get("name") or "").strip()
    type_ = (request.form.get("type") or "").strip()
    event_date = _parse_date(request.form.get("event_date"))
    end_date = _parse_date(request.form.get("end_date"))
    location = (request.form.get("location") or "").strip() or None
    description = (request.form.get("description") or "").strip() or None
    dynasty_id = (request.form.get("dynasty_id") or "").strip() or None
    image_url = _normalize_local_image_path(request.form.get("image_url"))
    participant_ids = _parse_int_list(request.form.getlist("participant_ids"))
    related_battle_ids = _parse_int_list(request.form.getlist("related_battle_ids"))

    image_file = request.files.get("image_file")
    if image_file and getattr(image_file, "filename", ""):
        try:
            image_url = save_image_local_path(image_file, "events")
        except UploadError as e:
            flash(f"Image upload failed: {e}", "error")
            return redirect(url_for("admin.event_edit", event_id=event_id))

    if not name:
        flash("Name is required.", "error")
        return redirect(url_for("admin.event_edit", event_id=event_id))
    if not type_:
        flash("Type is required.", "error")
        return redirect(url_for("admin.event_edit", event_id=event_id))
    try:
        _validate_max_length(name, 150, "Name")
        _validate_max_length(description, 5000, "Description")
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("admin.event_edit", event_id=event_id))

    did = None
    if dynasty_id:
        try:
            did = int(dynasty_id)
        except ValueError:
            flash("Invalid dynasty selected.", "error")
            return redirect(url_for("admin.event_edit", event_id=event_id))

    try:
        execute_query(
            """
            UPDATE Event
            SET name = %s,
                type = %s::event_type,
                event_date = %s,
                end_date = %s,
                location = %s,
                description = %s,
                image_url = %s,
                dynasty_id = %s
            WHERE event_id = %s
            """,
            (name, type_, event_date, end_date, location, description, image_url, did, event_id),
        )
        _sync_event_links(event_id, participant_ids, related_battle_ids)
        log_audit("Event", "UPDATE", event_id, current_user.username, f"Updated event '{name}'")
    except DatabaseError as e:
        flash(f"Failed to update event: {e}", "error")
        return redirect(url_for("admin.event_edit", event_id=event_id))

    flash("Event updated successfully.", "success")
    return redirect(url_for("admin.events_list"))


@admin_bp.route("/events/<int:event_id>/delete", methods=["POST"])
@login_required
@admin_required
def event_delete(event_id: int):
    try:
        execute_query("DELETE FROM Event WHERE event_id = %s", (event_id,))
        log_audit("Event", "DELETE", event_id, current_user.username, "Deleted event")
    except DatabaseError as e:
        flash(f"Failed to delete event: {e}", "error")
        return redirect(url_for("admin.events_list"))

    flash("Event deleted.", "success")
    return redirect(url_for("admin.events_list"))


def _normalize_database_url_for_pg_tools(url: str) -> str:
    """
    Convert SQLAlchemy / async driver URLs to a libpq URI for pg_dump and psql.
    Example: postgresql+psycopg2://... -> postgresql://...
    """
    u = (url or "").strip()
    if "://" not in u:
        return u
    scheme, rest = u.split("://", 1)
    lower = scheme.lower()
    if "+" in lower:
        base = lower.split("+", 1)[0]
        if base in ("postgres", "postgresql"):
            return f"postgresql://{rest}"
    if lower == "postgres":
        return f"postgresql://{rest}"
    return u


def _validate_libpq_database_url(database_url: str) -> None:
    """Ensure DATABASE_URL looks usable for pg_dump / libpq (after driver normalization)."""
    parsed = urlparse(database_url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ValueError("DATABASE_URL must start with postgres:// or postgresql://")
    db_name = (parsed.path or "").lstrip("/")
    if not db_name:
        raise ValueError("DATABASE_URL missing database name.")
    if not parsed.hostname or not parsed.username:
        raise ValueError("DATABASE_URL missing host or username.")


def clean_pg_dump(sql: str | None) -> str:
    """
    Remove pg_dump meta-command lines that are not SQL and can break restores.
    Data-only dumps usually omit these; kept as a safety net.
    """
    lines = (sql or "").splitlines()
    cleaned: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("\\restrict"):
            continue
        if stripped.startswith("\\unrestrict"):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def _split_sql_statements(sql: str) -> list[str]:
    """
    Split a SQL script into statements for psycopg2 (one execute per statement).
    Respects single-quoted string literals so semicolons inside values are not split.
    """
    parts: list[str] = []
    buf: list[str] = []
    in_single = False
    i = 0
    n = len(sql)
    while i < n:
        c = sql[i]
        if in_single:
            buf.append(c)
            if c == "'":
                if i + 1 < n and sql[i + 1] == "'":
                    buf.append("'")
                    i += 2
                    continue
                in_single = False
            i += 1
            continue
        if c == "'":
            in_single = True
            buf.append(c)
            i += 1
            continue
        if c == ";":
            stmt = "".join(buf).strip()
            if stmt:
                parts.append(stmt)
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


# Lowercase unquoted PostgreSQL table names (matches schema). user_account excluded — not backed up.
BACKUP_TABLES = [
    "dynasty",
    "person",
    "reign",
    "territory",
    "dynasty_territory",
    "event",
    "person_event",
    "parent_child",
    "relation",
    "succession",
    "event_relation",
    "edit_request",
    "audit_log",
]

RESTORE_ORDER = [
    "dynasty",
    "territory",
    "person",
    "reign",
    "event",
    "dynasty_territory",
    "person_event",
    "parent_child",
    "relation",
    "succession",
    "event_relation",
    "edit_request",
    "audit_log",
]

RESTORE_ALLOWED_TABLES_LOWER = frozenset(t.lower() for t in BACKUP_TABLES)

_FORBIDDEN_SQL_CONSTRUCTS_OUTSIDE_QUOTES = frozenset(
    (
        "SELECT",
        "DROP",
        "DELETE",
        "UPDATE",
        "TRUNCATE",
        "ALTER",
        "CREATE",
        "GRANT",
        "REVOKE",
        "COPY",
        "EXECUTE",
        "CALL",
        "DO",
        "PREPARE",
        "LISTEN",
        "NOTIFY",
        "VACUUM",
        "CLUSTER",
    )
)

_INSERT_TARGET_RE = re.compile(
    r"""
    ^\s*INSERT\s+INTO\s+(?:ONLY\s+)?
    (?:(?P<schema>[a-z_][a-z0-9_]*)\.)?
    (?:
        "(?P<quoted>(?:[^"]|"")*)"
        |
        (?P<bare>[a-z_][a-z0-9_]*)
    )
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)


def _truncate_catalog_tables_sql() -> str:
    """Truncate only catalog tables included in backups (never User_Account or other app tables)."""
    tables = ", ".join(RESTORE_ORDER)
    return f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE;"


def _sql_outside_single_quoted_strings(sql: str) -> str:
    """Concatenate regions outside standard single-quoted literals for keyword safety scans."""
    parts: list[str] = []
    i = 0
    n = len(sql)
    chunk_start = 0
    while i < n:
        if sql[i] == "'":
            parts.append(sql[chunk_start:i])
            i += 1
            while i < n:
                if sql[i] == "'":
                    if i + 1 < n and sql[i + 1] == "'":
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            chunk_start = i
            continue
        i += 1
    parts.append(sql[chunk_start:])
    return " ".join(parts)


def _validate_restore_insert_statement(
    stmt: str,
    *,
    expected_table_lower: str | None = None,
) -> str:
    """
    Allow only INSERT into BACKUP_TABLES in schema public (pg_dump --data-only style).
    Blocks DDL, DML other than INSERT, subqueries (SELECT), and User_Account / other tables.
    """
    raw = (stmt or "").strip()
    if not raw:
        raise ValueError("Empty SQL statement in backup.")

    outside = _sql_outside_single_quoted_strings(raw)
    outside_upper = outside.upper()
    if outside_upper.count("INSERT INTO") != 1:
        raise ValueError("Each backup statement must be exactly one INSERT INTO … statement.")

    insert_pos = outside_upper.index("INSERT INTO")
    if insert_pos < 0:
        raise ValueError("Expected INSERT INTO … statement.")
    prefix = outside_upper[:insert_pos]
    if prefix.strip():
        raise ValueError("Restore only allows INSERT statements with no leading SQL.")

    tail_scan = outside_upper[insert_pos + len("INSERT INTO") :]
    for word in _FORBIDDEN_SQL_CONSTRUCTS_OUTSIDE_QUOTES:
        if re.search(rf"\b{re.escape(word)}\b", tail_scan):
            raise ValueError(f"Disallowed SQL in backup data restore: {word}")

    m = _INSERT_TARGET_RE.match(raw)
    if not m:
        raise ValueError("Malformed INSERT in backup (expected pg_dump column-inserts shape).")

    schema = (m.group("schema") or "").lower()
    if schema and schema != "public":
        raise ValueError("Restore only allows inserts into schema public.")

    quoted = m.group("quoted")
    bare = m.group("bare")
    if quoted is not None:
        tname = quoted.replace('""', '"').lower()
    else:
        tname = (bare or "").lower()

    if tname not in RESTORE_ALLOWED_TABLES_LOWER:
        raise ValueError(f"Restore cannot load table {tname!r} (not part of catalog backups).")

    if expected_table_lower is not None and tname != expected_table_lower:
        raise ValueError(
            f"Backup chunk for {expected_table_lower!r} contained INSERT into {tname!r}."
        )

    return raw


def _decode_validate_split_table_sql(
    encoded_b64: str,
    *,
    expected_table_lower: str | None,
) -> list[str]:
    sql = base64.b64decode(encoded_b64.encode("utf-8")).decode("utf-8")
    sql = clean_pg_dump(sql)
    if not sql.strip():
        return []
    validated: list[str] = []
    for stmt in _split_sql_statements(sql):
        validated.append(
            _validate_restore_insert_statement(stmt, expected_table_lower=expected_table_lower)
        )
    return validated


def _dump_table(table: str, libpq_url: str) -> str:
    """Run pg_dump for a single table; return cleaned SQL (empty if no data statements)."""
    result = subprocess.run(
        [
            "pg_dump",
            "-d",
            libpq_url,
            "-f",
            "-",
            "--data-only",
            "--column-inserts",
            "--no-owner",
            "--no-privileges",
            "--disable-triggers",
            "-t",
            f"public.{table}",
        ],
        env=os.environ.copy(),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"pg_dump failed for {table}: {err[:400]}")
    sql = clean_pg_dump(result.stdout or "")
    if "insert into" not in sql.lower():
        return ""
    return sql


@admin_bp.route("/backup", methods=["POST"])
@login_required
@admin_required
def backup_database():
    """Per-table SQL backups in a timestamped folder → Firebase RTDB + Supabase Storage."""
    database_url = (os.getenv("DATABASE_URL") or "").strip()
    if not database_url:
        message = "Backup failed: DATABASE_URL is not configured."
        flash(message, "error")
        log_audit("DATABASE", "BACKUP", None, current_user.username, message)
        return redirect(url_for("admin.dashboard"))

    try:
        libpq_url = _normalize_database_url_for_pg_tools(database_url)
        _validate_libpq_database_url(libpq_url)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        folder_name = f"backup_{timestamp}"

        table_dumps: dict[str, str] = {}
        table_errors: list[str] = []

        for table in BACKUP_TABLES:
            try:
                table_dumps[table] = _dump_table(table, libpq_url)
            except Exception as e:
                table_errors.append(f"{table}: {e}")

        if table_errors:
            message = f"Backup failed — pg_dump errors: {'; '.join(table_errors)}"
            flash(message, "error")
            log_audit("DATABASE", "BACKUP", None, current_user.username, message)
            return redirect(url_for("admin.dashboard"))

        if not table_dumps:
            flash("Backup failed — no tables dumped.", "error")
            log_audit("DATABASE", "BACKUP", None, current_user.username, "no tables")
            return redirect(url_for("admin.dashboard"))

        from firebase_admin import db as rtdb

        firebase_ref_path = None
        upload_errors: list[str] = []
        total_size = 0
        tables_data: dict[str, dict[str, str]] = {}
        for table, sql in table_dumps.items():
            raw = sql.encode("utf-8")
            total_size += len(raw)
            tables_data[table] = {
                "content_b64": base64.b64encode(raw).decode("utf-8") if raw else "",
            }

        try:
            key = folder_name.replace(".", "_").replace("-", "_")
            ref = rtdb.reference(f"/backups/{key}")
            ref.set(
                {
                    "metadata": {
                        "folder": folder_name,
                        "created_at": datetime.utcnow().isoformat(),
                        "total_tables": len(table_dumps),
                        "size_kb": round(total_size / 1024, 2),
                        "tables": list(table_dumps.keys()),
                    },
                    "tables": tables_data,
                }
            )
            firebase_ref_path = f"/backups/{key}"
        except Exception as e:
            upload_errors.append(f"Firebase: {e}")

        supabase_ok = 0
        try:
            sb = get_supabase_client()
            bucket = sb.storage.from_(SUPABASE_BACKUP_BUCKET)
            for table, sql in table_dumps.items():
                path = f"{folder_name}/{table}.sql"
                bucket.upload(
                    path=path,
                    file=sql.encode("utf-8"),
                    file_options={
                        "content-type": "text/plain; charset=utf-8",
                        "upsert": "true",
                    },
                )
                supabase_ok += 1
        except Exception as e:
            upload_errors.append(f"Supabase: {e}")

        if not firebase_ref_path and supabase_ok == 0:
            message = f"Backup failed on all destinations: {'; '.join(upload_errors)}"
            flash(message, "error")
            log_audit("DATABASE", "BACKUP", None, current_user.username, message)
            return redirect(url_for("admin.dashboard"))

        details_parts: list[str] = []
        if firebase_ref_path:
            details_parts.append(f"Firebase RTDB: {firebase_ref_path} ({len(table_dumps)} tables)")
        if supabase_ok:
            details_parts.append(f"Supabase: {folder_name}/ ({supabase_ok} files)")
        if upload_errors:
            details_parts.append(f"Errors: {'; '.join(upload_errors)}")
        details = " | ".join(details_parts)

        log_audit("DATABASE", "BACKUP", None, current_user.username, details)
        if upload_errors:
            flash(
                f"Backup partial — folder {folder_name}. Warning: {'; '.join(upload_errors)}",
                "warning",
            )
        else:
            flash(f"Backup complete — {folder_name} ({len(table_dumps)} tables) saved.", "success")
    except Exception as e:
        message = f"Backup failed: {type(e).__name__}: {e}"
        flash(message, "error")
        log_audit("DATABASE", "BACKUP", None, current_user.username, message)
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/backups")
@login_required
@admin_required
def backup_list():
    backups_grouped: dict[str, list[dict]] = {}
    try:
        sb = get_supabase_client()
        bucket = sb.storage.from_(SUPABASE_BACKUP_BUCKET)
        top = bucket.list("") or []
        grouped = defaultdict(list)

        for entry in top:
            name = (entry.get("name") or "").strip()
            if not name:
                continue
            if name.endswith(".sql"):
                if "/" in name:
                    folder_key = name.rsplit("/", 1)[0]
                else:
                    folder_key = ""
                grouped[folder_key].append({**entry, "path": name})
                continue
            children = bucket.list(name) or []
            for ch in children:
                base = (ch.get("name") or "").strip()
                if base.endswith(".sql"):
                    full_path = f"{name}/{base}"
                    grouped[name].append({**ch, "path": full_path})

        backups_grouped = dict(sorted(grouped.items(), key=lambda kv: kv[0], reverse=True))
    except Exception as e:
        flash(f"Could not load backups from Supabase: {e}", "error")
        backups_grouped = {}

    return render_template("admin/backup_list.html", backups_grouped=backups_grouped)


@admin_bp.route("/backups/<path:filename>/download", methods=["POST"])
@login_required
@admin_required
def backup_download(filename: str):
    try:
        sb = get_supabase_client()
        signed = sb.storage.from_(SUPABASE_BACKUP_BUCKET).create_signed_url(filename, expires_in=300)
        url = signed.get("signedURL") or signed.get("signedUrl", "")
        if not url:
            flash("Could not generate download link.", "error")
            return redirect(url_for("admin.backup_list"))
        return redirect(url)
    except Exception as e:
        flash(f"Could not generate download link: {e}", "error")
        return redirect(url_for("admin.backup_list"))


@admin_bp.route("/backups/firebase")
@login_required
@admin_required
def firebase_backups():
    try:
        from firebase_admin import db

        ref = db.reference("/backups")
        data = ref.get()
        backups = []
        if data:
            for key, val in data.items():
                if not isinstance(val, dict):
                    continue
                tables_blob = val.get("tables")
                if isinstance(tables_blob, dict):
                    meta = val.get("metadata") or {}
                    tables_detail: list[dict] = []
                    for tname, tnode in tables_blob.items():
                        b64 = ""
                        if isinstance(tnode, dict):
                            b64 = str(tnode.get("content_b64") or "")
                        raw_len = 0
                        if b64:
                            try:
                                raw_len = len(base64.b64decode(b64.encode("utf-8")))
                            except Exception:
                                raw_len = 0
                        tables_detail.append(
                            {
                                "name": tname,
                                "size_kb": round(raw_len / 1024, 2),
                            }
                        )
                    backups.append(
                        {
                            "key": key,
                            "multi": True,
                            "folder": meta.get("folder", key),
                            "filename": meta.get("folder", key),
                            "created_at": meta.get("created_at", ""),
                            "size_kb": meta.get("size_kb", 0),
                            "total_tables": meta.get("total_tables", len(tables_blob)),
                            "tables": meta.get("tables", list(tables_blob.keys())),
                            "tables_detail": sorted(tables_detail, key=lambda x: x["name"]),
                        }
                    )
                else:
                    backups.append(
                        {
                            "key": key,
                            "multi": False,
                            "folder": val.get("filename", key),
                            "filename": val.get("filename", key),
                            "created_at": val.get("created_at", ""),
                            "size_kb": val.get("size_kb", 0),
                            "total_tables": None,
                            "tables": [],
                            "tables_detail": [],
                        }
                    )
            backups.sort(key=lambda x: (x.get("created_at") or ""), reverse=True)
    except Exception as e:
        flash(f"Could not load Firebase backups: {e}", "error")
        backups = []

    return render_template("admin/firebase_backups.html", backups=backups)


@admin_bp.route("/backups/firebase/<key>/delete", methods=["POST"])
@login_required
@admin_required
def firebase_backup_delete(key: str):
    try:
        from firebase_admin import db

        db.reference(f"/backups/{key}").delete()
        flash("Backup deleted from Firebase.", "success")
    except Exception as e:
        flash(f"Delete failed: {e}", "error")
    return redirect(url_for("admin.firebase_backups"))


@admin_bp.route("/backups/firebase/<key>/restore", methods=["POST"])
@login_required
@admin_required
def firebase_backup_restore(key: str):
    password = request.form.get("password") or ""
    rows = execute_query("SELECT password FROM User_Account WHERE user_id = %s", (current_user.id,))
    if not rows or not check_password_hash(str(rows[0][0]), password):
        flash("Incorrect password. Restore cancelled.", "error")
        return redirect(url_for("admin.firebase_backups"))

    try:
        from firebase_admin import db as rtdb

        ref = rtdb.reference(f"/backups/{key}")
        data = ref.get()
        if not data or not isinstance(data, dict):
            flash("Backup not found.", "error")
            return redirect(url_for("admin.firebase_backups"))
    except Exception as e:
        flash(f"Failed to fetch backup from Firebase: {e}", "error")
        return redirect(url_for("admin.firebase_backups"))

    database_url = (os.environ.get("DATABASE_URL") or "").strip()
    if not database_url:
        flash("Restore failed: DATABASE_URL is not configured.", "error")
        return redirect(url_for("admin.firebase_backups"))

    try:
        libpq_url = _normalize_database_url_for_pg_tools(database_url)
        _validate_libpq_database_url(libpq_url)
    except ValueError as e:
        flash(f"Restore failed: invalid DATABASE_URL ({e}).", "error")
        return redirect(url_for("admin.firebase_backups"))

    folder_label = data.get("metadata", {}).get("folder", key) if isinstance(data.get("metadata"), dict) else key
    tables_payload = data.get("tables")

    statements_to_run: list[str] = []
    restore_details = ""

    try:
        if isinstance(tables_payload, dict):
            for table in RESTORE_ORDER:
                if table not in tables_payload:
                    continue
                tnode = tables_payload[table]
                if not isinstance(tnode, dict):
                    continue
                encoded = str(tnode.get("content_b64") or "")
                if not encoded.strip():
                    continue
                statements_to_run.extend(
                    _decode_validate_split_table_sql(encoded, expected_table_lower=table.lower())
                )
            if not statements_to_run:
                flash(
                    "Restore aborted: backup contained no valid INSERT data for catalog tables.",
                    "error",
                )
                return redirect(url_for("admin.firebase_backups"))
            restore_details = f"Restored multi-table backup: {folder_label}"

        elif "content_b64" in data:
            try:
                sql_content = base64.b64decode(str(data["content_b64"]).encode("utf-8")).decode("utf-8")
            except Exception as e:
                flash(f"Failed to decode backup content: {e}", "error")
                return redirect(url_for("admin.firebase_backups"))
            sql_content = clean_pg_dump(sql_content)
            for stmt in _split_sql_statements(sql_content):
                statements_to_run.append(_validate_restore_insert_statement(stmt, expected_table_lower=None))
            if not statements_to_run:
                flash("Restore aborted: legacy backup had no valid INSERT statements.", "error")
                return redirect(url_for("admin.firebase_backups"))
            filename = data.get("filename", key)
            restore_details = f"Restored legacy Firebase backup: {filename}"

        elif "content" in data:
            sql_content = clean_pg_dump(str(data["content"] or ""))
            for stmt in _split_sql_statements(sql_content):
                statements_to_run.append(_validate_restore_insert_statement(stmt, expected_table_lower=None))
            if not statements_to_run:
                flash("Restore aborted: legacy backup had no valid INSERT statements.", "error")
                return redirect(url_for("admin.firebase_backups"))
            filename = data.get("filename", key)
            restore_details = f"Restored legacy Firebase backup: {filename}"

        else:
            flash(
                "Backup not found or uses an unknown format (expected tables, content_b64, or content).",
                "error",
            )
            return redirect(url_for("admin.firebase_backups"))

    except ValueError as e:
        flash(f"Restore aborted: invalid or unsafe backup SQL ({e})", "error")
        return redirect(url_for("admin.firebase_backups"))

    conn = None
    cur = None
    try:
        conn = psycopg2.connect(libpq_url)
        conn.autocommit = False
        cur = conn.cursor()

        cur.execute(_truncate_catalog_tables_sql())

        for stmt in statements_to_run:
            cur.execute(stmt)

        cur.execute(
            """
            INSERT INTO Audit_Log (table_name, operation, performed_by, details)
            VALUES ('DATABASE', 'RESTORE', %s, %s)
            """,
            (current_user.username, restore_details),
        )
        conn.commit()
        label = folder_label if isinstance(tables_payload, dict) else data.get("filename", key)
        flash(
            f"Catalog data restored from {label}. "
            "User accounts and schema were not modified by this operation.",
            "success",
        )
        return redirect(url_for("admin.dashboard"))

    except Exception as e:
        if conn is not None:
            conn.rollback()
        flash(f"Restore failed: {e}", "error")
        return redirect(url_for("admin.firebase_backups"))
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


@admin_bp.route("/edit-requests")
@login_required
@admin_required
def edit_requests_list():
    pending_rows = execute_query(
        """
        SELECT request_id, entity_type, entity_id, field_name, old_value, new_value, reason, submitted_by, submitted_at
        FROM Edit_Request
        WHERE status = 'pending'
        ORDER BY submitted_at DESC
        """
    )
    return render_template("admin/edit_requests.html", requests=pending_rows, pending_count=len(pending_rows))


@admin_bp.route("/edit-requests/<int:request_id>/approve", methods=["POST"])
@login_required
@admin_required
def edit_request_approve(request_id: int):
    rows = execute_query(
        """
        SELECT request_id, entity_type, entity_id, field_name, old_value, new_value, reason, submitted_by, status
        FROM Edit_Request
        WHERE request_id = %s
        """,
        (request_id,),
    )
    if not rows:
        flash("Edit request not found.", "error")
        return redirect(url_for("admin.edit_requests_list"))
    req = rows[0]
    if req[8] != "pending":
        flash("This request has already been reviewed.", "error")
        return redirect(url_for("admin.edit_requests_list"))

    entity_type = str(req[1])
    entity_id = int(req[2])
    field_name = str(req[3])
    new_value = str(req[5])

    allowed_fields = {
        "person": {"full_name", "biography", "birth_date", "death_date"},
        "dynasty": {"name", "description", "start_year", "end_year"},
    }
    table_by_entity = {"person": "Person", "dynasty": "Dynasty"}
    id_col_by_entity = {"person": "person_id", "dynasty": "dynasty_id"}

    if entity_type not in allowed_fields or field_name not in allowed_fields[entity_type]:
        flash("Invalid edit request payload.", "error")
        return redirect(url_for("admin.edit_requests_list"))

    try:
        normalized_value: object = new_value
        if field_name in {"start_year", "end_year"}:
            normalized_value = int(new_value)
        elif field_name in {"birth_date", "death_date"}:
            normalized_value = new_value

        update_sql = f"UPDATE {table_by_entity[entity_type]} SET {field_name} = %s WHERE {id_col_by_entity[entity_type]} = %s"
        execute_query(update_sql, (normalized_value, entity_id))
        execute_query(
            """
            UPDATE Edit_Request
            SET status = 'approved', reviewed_by = %s, reviewed_at = NOW()
            WHERE request_id = %s
            """,
            (current_user.username, request_id),
        )
        log_audit(
            table_by_entity[entity_type],
            "UPDATE",
            entity_id,
            current_user.username,
            f"Approved edit request #{request_id} for {field_name}",
        )
        flash("Edit request approved and applied.", "success")
    except Exception as e:
        flash(f"Failed to approve request: {e}", "error")
    return redirect(url_for("admin.edit_requests_list"))


@admin_bp.route("/edit-requests/<int:request_id>/decline", methods=["POST"])
@login_required
@admin_required
def edit_request_decline(request_id: int):
    rows = execute_query(
        """
        SELECT request_id, entity_type, entity_id, field_name, status
        FROM Edit_Request
        WHERE request_id = %s
        """,
        (request_id,),
    )
    if not rows:
        flash("Edit request not found.", "error")
        return redirect(url_for("admin.edit_requests_list"))
    req = rows[0]
    if req[4] != "pending":
        flash("This request has already been reviewed.", "error")
        return redirect(url_for("admin.edit_requests_list"))

    execute_query(
        """
        UPDATE Edit_Request
        SET status = 'declined', reviewed_by = %s, reviewed_at = NOW()
        WHERE request_id = %s
        """,
        (current_user.username, request_id),
    )
    log_audit(
        "Edit_Request",
        "UPDATE",
        int(request_id),
        current_user.username,
        f"Declined edit request #{request_id} for {req[1]}:{req[2]} field {req[3]}",
    )
    flash("Edit request declined.", "success")
    return redirect(url_for("admin.edit_requests_list"))


@admin_bp.route("/clear-db")
@login_required
@admin_required
def clear_db_confirm_page():
    return render_template("admin/clear_db_confirm.html")


@admin_bp.route("/clear-db/confirm", methods=["POST"])
@login_required
@admin_required
def clear_db_confirm():
    confirm_text = (request.form.get("confirm_text") or "").strip()
    password = request.form.get("password") or ""
    if confirm_text != "DELETE EVERYTHING":
        flash("Confirmation text did not match.", "error")
        return redirect(url_for("admin.clear_db_confirm_page"))

    rows = execute_query(
        """
        SELECT password
        FROM User_Account
        WHERE user_id = %s
        """,
        (current_user.id,),
    )
    if not rows:
        flash("Admin account not found.", "error")
        return redirect(url_for("admin.clear_db_confirm_page"))
    if not check_password_hash(str(rows[0][0]), password):
        flash("Incorrect password.", "error")
        return redirect(url_for("admin.clear_db_confirm_page"))

    try:
        execute_query(
            """
            TRUNCATE TABLE Dynasty_Territory CASCADE;
            TRUNCATE TABLE Person_Event CASCADE;
            TRUNCATE TABLE Parent_Child CASCADE;
            TRUNCATE TABLE Succession CASCADE;
            TRUNCATE TABLE Audit_Log CASCADE;
            TRUNCATE TABLE Edit_Request CASCADE;
            TRUNCATE TABLE Relation CASCADE;
            TRUNCATE TABLE Event CASCADE;
            TRUNCATE TABLE Territory CASCADE;
            TRUNCATE TABLE Reign CASCADE;
            TRUNCATE TABLE Person CASCADE;
            TRUNCATE TABLE Dynasty CASCADE;
            """
        )
        execute_query(
            """
            INSERT INTO Audit_Log (table_name, operation, performed_by, details)
            VALUES ('DATABASE', 'CLEAR', %s, 'Full database clear performed')
            """,
            (current_user.username,),
        )
    except Exception as e:
        flash(f"Clear failed: {e}", "error")
        return redirect(url_for("admin.clear_db_confirm_page"))

    flash("Database cleared successfully. All records have been deleted.", "warning")
    return redirect(url_for("admin.dashboard"))