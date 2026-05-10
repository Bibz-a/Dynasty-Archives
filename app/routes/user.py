from __future__ import annotations

from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.db import execute_query

user_bp = Blueprint("user", __name__)

_PERSON_SUGGEST_FIELDS = {
    "full_name": 1,
    "biography": 4,
    "birth_date": 2,
    "death_date": 3,
}
_DYNASTY_SUGGEST_FIELDS = {
    "name": 1,
    "description": 4,
    "start_year": 2,
    "end_year": 3,
}


def viewer_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not getattr(current_user, "is_authenticated", False):
            flash("You must be logged in to do this.", "error")
            return redirect(url_for("auth.login"))
        return view_func(*args, **kwargs)

    return wrapper


@user_bp.route("/")
def home():
    dynasties_count = execute_query("SELECT COUNT(*) FROM Dynasty")[0][0]
    rulers_count = execute_query("SELECT COUNT(*) FROM Person")[0][0]
    events_count = execute_query("SELECT COUNT(*) FROM Event")[0][0]
    return render_template(
        "home.html",
        stats={
            "dynasties": int(dynasties_count),
            "rulers": int(rulers_count),
            "events": int(events_count),
        },
    )


@user_bp.route("/rulers")
def rulers():
    search = (request.args.get("search") or "").strip()
    no_events = (request.args.get("no_events") or "").strip() == "1"
    dynasty_id = (request.args.get("dynasty_id") or "").strip()
    title = (request.args.get("title") or "").strip()
    era_start = (request.args.get("era_start") or "").strip()
    era_end = (request.args.get("era_end") or "").strip()
    sort = (request.args.get("sort") or "name").strip()
    params = []
    clauses = []
    if search:
        clauses.append("p.full_name ILIKE %s")
        params.append(f"%{search}%")
    if no_events:
        clauses.append("p.person_id NOT IN (SELECT person_id FROM Person_Event)")
    if dynasty_id:
        clauses.append("p.dynasty_id = %s")
        params.append(int(dynasty_id))
    if title:
        clauses.append("r.title ILIKE %s")
        params.append(f"%{title}%")
    if era_start:
        clauses.append("EXTRACT(YEAR FROM r.start_date) >= %s")
        params.append(int(era_start))
    if era_end:
        clauses.append("EXTRACT(YEAR FROM COALESCE(r.end_date, CURRENT_DATE)) <= %s")
        params.append(int(era_end))

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sort_map = {
        "name": "p.full_name",
        "reign_start": "r.start_date NULLS LAST",
        "reign_length": "(COALESCE(r.end_date, CURRENT_DATE) - r.start_date) DESC NULLS LAST",
    }
    order_by = sort_map.get(sort, "p.full_name")
    dynasties = execute_query("SELECT dynasty_id, name FROM Dynasty ORDER BY name LIMIT 200")

    data = execute_query(
        f"""
        SELECT
            p.person_id,
            p.full_name,
            d.name AS dynasty_name,
            r.title,
            r.start_date::text,
            r.end_date::text,
            p.birth_date::text,
            p.death_date::text,
            p.image_url
        FROM Person p
        JOIN Dynasty d ON d.dynasty_id = p.dynasty_id
        LEFT JOIN Reign r ON r.person_id = p.person_id
        {where}
        ORDER BY {order_by}
        LIMIT 200
        """,
        tuple(params) if params else None,
    )
    return render_template(
        "rulers.html",
        rulers=data,
        search=search,
        no_events=no_events,
        dynasty_id=dynasty_id,
        title=title,
        era_start=era_start,
        era_end=era_end,
        sort=sort,
        dynasties=dynasties,
    )


@user_bp.route("/rulers/<int:person_id>")
def ruler_detail(person_id: int):
    person_rows = execute_query(
        """
        SELECT
            p.person_id, p.full_name, p.birth_date::text, p.death_date::text, p.biography, p.image_url,
            d.dynasty_id, d.name
        FROM Person p
        JOIN Dynasty d ON d.dynasty_id = p.dynasty_id
        WHERE p.person_id = %s
        """,
        (person_id,),
    )
    if not person_rows:
        flash("Ruler not found.", "error")
        return redirect(url_for("user.rulers"))
    person = person_rows[0]

    reigns = execute_query(
        """
        SELECT reign_id, title, capital, start_date::text, end_date::text, notes
        FROM Reign
        WHERE person_id = %s
        ORDER BY start_date
        """,
        (person_id,),
    )

    parents = execute_query(
        """
        SELECT p.person_id, p.full_name
        FROM Parent_Child pc
        JOIN Person p ON p.person_id = pc.parent_id
        WHERE pc.child_id = %s
        ORDER BY p.full_name
        """,
        (person_id,),
    )
    children = execute_query(
        """
        SELECT p.person_id, p.full_name
        FROM Parent_Child pc
        JOIN Person p ON p.person_id = pc.child_id
        WHERE pc.parent_id = %s
        ORDER BY p.full_name
        """,
        (person_id,),
    )

    events = execute_query(
        """
        SELECT e.event_id, e.name, e.type, e.event_date::text, e.location, pe.role
        FROM Person_Event pe
        JOIN Event e ON e.event_id = pe.event_id
        WHERE pe.person_id = %s
        ORDER BY e.event_date NULLS LAST, e.name
        """,
        (person_id,),
    )

    succeeded = execute_query(
        """
        SELECT s.succession_id, pred.person_id, pred.full_name, s.type, s.year, s.notes
        FROM Succession s
        JOIN Person pred ON pred.person_id = s.predecessor_id
        WHERE s.successor_id = %s
        ORDER BY s.year NULLS LAST
        """,
        (person_id,),
    )
    successors = execute_query(
        """
        SELECT s.succession_id, succ.person_id, succ.full_name, s.type, s.year, s.notes
        FROM Succession s
        JOIN Person succ ON succ.person_id = s.successor_id
        WHERE s.predecessor_id = %s
        ORDER BY s.year NULLS LAST
        """,
        (person_id,),
    )
    spouses = execute_query(
        """
        SELECT
            r.relation_id,
            CASE
                WHEN r.person_a_id = %s THEN p2.person_id
                ELSE p1.person_id
            END AS spouse_id,
            CASE
                WHEN r.person_a_id = %s THEN p2.full_name
                ELSE p1.full_name
            END AS spouse_name,
            r.start_year,
            r.end_year,
            r.notes
        FROM Relation r
        JOIN Person p1 ON p1.person_id = r.person_a_id
        JOIN Person p2 ON p2.person_id = r.person_b_id
        WHERE r.relation_type = 'spouse'
          AND (%s IN (r.person_a_id, r.person_b_id))
        ORDER BY r.start_year NULLS LAST, spouse_name
        LIMIT 200
        """,
        (person_id, person_id, person_id),
    )
    return render_template(
        "ruler_detail.html",
        person=person,
        reigns=reigns,
        parents=parents,
        children=children,
        events=events,
        succeeded=succeeded,
        successors=successors,
        spouses=spouses,
    )

@user_bp.route("/dynasties")
def dynasties():
    data = execute_query(
        """
        SELECT dynasty_id, name, start_year, end_year, description, image_url
        FROM Dynasty
        ORDER BY start_year
        """,
    )
    return render_template("dynasties.html", dynasties=data)


@user_bp.route("/dynasties/<int:dynasty_id>")
def dynasty_detail(dynasty_id: int):
    dyn_rows = execute_query(
        """
        SELECT dynasty_id, name, start_year, end_year, description, image_url
        FROM Dynasty
        WHERE dynasty_id = %s
        """,
        (dynasty_id,),
    )
    if not dyn_rows:
        flash("Dynasty not found.", "error")
        return redirect(url_for("user.dynasties"))
    dynasty = dyn_rows[0]

    rulers = execute_query(
        """
        SELECT p.person_id, p.full_name, r.title, r.start_date::text, r.end_date::text
        FROM Person p
        JOIN Reign r ON r.person_id = p.person_id
        WHERE p.dynasty_id = %s
        ORDER BY r.start_date
        """,
        (dynasty_id,),
    )

    territories = execute_query(
        """
        SELECT t.territory_id, t.name, t.region, dt.start_year, dt.end_year
        FROM Dynasty_Territory dt
        JOIN Territory t ON t.territory_id = dt.territory_id
        WHERE dt.dynasty_id = %s
        ORDER BY dt.start_year NULLS LAST, t.name
        """,
        (dynasty_id,),
    )

    events = execute_query(
        """
        SELECT event_id, name, type, event_date::text, location
        FROM Event
        WHERE dynasty_id = %s
        ORDER BY event_date NULLS LAST, name
        """,
        (dynasty_id,),
    )

    return render_template(
        "dynasty_detail.html",
        dynasty=dynasty,
        rulers=rulers,
        territories=territories,
        events=events,
    )


@user_bp.route("/events")
def events():
    event_type = (request.args.get("type") or "").strip()
    where = ""
    params = None
    if event_type:
        where = "WHERE e.type = %s"
        params = (event_type,)

    data = execute_query(
        f"""
        SELECT e.event_id, e.name, e.type, e.event_date::text, e.location, d.name, e.image_url
        FROM Event e
        LEFT JOIN Dynasty d ON d.dynasty_id = e.dynasty_id
        {where}
        ORDER BY e.event_date NULLS LAST, e.name
        """,
        params,
    )

    type_rows = execute_query("SELECT DISTINCT type::text FROM Event ORDER BY type::text")
    types = [r[0] for r in type_rows]
    return render_template("events.html", events=data, types=types, selected_type=event_type)


@user_bp.route("/events/<int:event_id>")
def event_detail(event_id: int):
    rows = execute_query(
        """
        SELECT e.event_id, e.name, e.type::text, e.event_date::text, e.end_date::text, e.location,
               e.description, e.image_url, d.dynasty_id, d.name
        FROM Event e
        LEFT JOIN Dynasty d ON d.dynasty_id = e.dynasty_id
        WHERE e.event_id = %s
        """,
        (event_id,),
    )
    if not rows:
        flash("Event not found.", "error")
        return redirect(url_for("user.events"))
    return render_template("event_detail.html", event=rows[0])


@user_bp.route("/timeline")
def timeline():
    start_year = (request.args.get("start_year") or "").strip()
    end_year = (request.args.get("end_year") or "").strip()
    emperor_id = (request.args.get("emperor_id") or "").strip()
    dynasty_id = (request.args.get("dynasty_id") or "").strip()
    event_type = (request.args.get("event_type") or "").strip()
    view = (request.args.get("view") or "list").strip()
    clauses = []
    params = []

    if start_year:
        clauses.append("EXTRACT(YEAR FROM e.event_date) >= %s")
        params.append(int(start_year))
    if end_year:
        clauses.append("EXTRACT(YEAR FROM e.event_date) <= %s")
        params.append(int(end_year))
    if emperor_id:
        clauses.append("EXISTS (SELECT 1 FROM Person_Event pe WHERE pe.event_id = e.event_id AND pe.person_id = %s)")
        params.append(int(emperor_id))
    if dynasty_id:
        clauses.append("e.dynasty_id = %s")
        params.append(int(dynasty_id))
    if event_type:
        clauses.append("e.type::text = %s")
        params.append(event_type)

    where = ""
    if clauses:
        where = "WHERE " + " AND ".join(clauses)

    data = execute_query(
        f"""
        SELECT e.event_id, e.name, e.type, e.event_date::text, e.location, d.name
        FROM Event e
        LEFT JOIN Dynasty d ON d.dynasty_id = e.dynasty_id
        {where}
        ORDER BY e.event_date
        LIMIT 200
        """,
        tuple(params) if params else None,
    )
    rulers = execute_query("SELECT person_id, full_name FROM Person ORDER BY full_name LIMIT 200")
    dynasties = execute_query("SELECT dynasty_id, name FROM Dynasty ORDER BY name LIMIT 200")
    types = execute_query("SELECT DISTINCT type::text FROM Event ORDER BY type::text LIMIT 200")
    return render_template(
        "timeline.html",
        events=data,
        start_year=start_year,
        end_year=end_year,
        emperor_id=emperor_id,
        dynasty_id=dynasty_id,
        event_type=event_type,
        rulers=rulers,
        dynasties=dynasties,
        types=[t[0] for t in types],
        view=view if view in {"list", "visual"} else "list",
    )


@user_bp.route("/territories")
def territories():
    data = execute_query(
        """
        SELECT
            t.territory_id,
            t.name,
            t.region,
            t.image_url,
            COALESCE(agg.dynasties, '') AS dynasties
        FROM Territory t
        LEFT JOIN (
            SELECT dt.territory_id,
                   STRING_AGG(DISTINCT d.name, ', ' ORDER BY d.name) AS dynasties
            FROM Dynasty_Territory dt
            JOIN Dynasty d ON d.dynasty_id = dt.dynasty_id
            GROUP BY dt.territory_id
        ) agg ON agg.territory_id = t.territory_id
        ORDER BY t.name
        LIMIT 200
        """,
    )
    return render_template("territories.html", territories=data)


@user_bp.route("/territories/<int:territory_id>")
def territory_detail(territory_id: int):
    terr_rows = execute_query(
        """
        SELECT territory_id, name, region, modern_name, description
        FROM Territory
        WHERE territory_id = %s
        """,
        (territory_id,),
    )
    if not terr_rows:
        flash("Territory not found.", "error")
        return redirect(url_for("user.territories"))
    territory = terr_rows[0]
    control_timeline = execute_query(
        """
        SELECT d.dynasty_id, d.name, dt.start_year, dt.end_year
        FROM Dynasty_Territory dt
        JOIN Dynasty d ON d.dynasty_id = dt.dynasty_id
        WHERE dt.territory_id = %s
        ORDER BY dt.start_year NULLS LAST, d.name
        LIMIT 200
        """,
        (territory_id,),
    )
    return render_template("territory_detail.html", territory=territory, control_timeline=control_timeline)


@user_bp.route("/rulers/<int:person_id>/suggest", methods=["GET", "POST"])
@viewer_required
def suggest_ruler_edit(person_id: int):
    person_rows = execute_query(
        """
        SELECT person_id, full_name, birth_date::text, death_date::text, biography
        FROM Person
        WHERE person_id = %s
        """,
        (person_id,),
    )
    if not person_rows:
        flash("Ruler not found.", "error")
        return redirect(url_for("user.rulers"))
    person = person_rows[0]

    if request.method == "GET":
        current_values = {
            "full_name": person[1],
            "biography": person[4],
            "birth_date": person[2],
            "death_date": person[3],
        }
        return render_template(
            "suggest_edit.html",
            entity_type="person",
            entity_id=person_id,
            entity_name=person[1],
            current_values=current_values,
            fields=list(_PERSON_SUGGEST_FIELDS.keys()),
            back_url=url_for("user.ruler_detail", person_id=person_id),
        )

    field_name = (request.form.get("field_name") or "").strip()
    new_value = (request.form.get("new_value") or "").strip()
    reason = (request.form.get("reason") or "").strip() or None
    if field_name not in _PERSON_SUGGEST_FIELDS:
        flash("Invalid field selected.", "error")
        return redirect(url_for("user.suggest_ruler_edit", person_id=person_id))
    if not new_value:
        flash("Please provide a suggested new value.", "error")
        return redirect(url_for("user.suggest_ruler_edit", person_id=person_id))

    old_value_raw = person[_PERSON_SUGGEST_FIELDS[field_name]]
    old_value = str(old_value_raw) if old_value_raw is not None else None
    submitted_by = current_user.username
    execute_query(
        """
        INSERT INTO Edit_Request (entity_type, entity_id, field_name, old_value, new_value, reason, submitted_by, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
        """,
        ("person", person_id, field_name, old_value, new_value, reason, submitted_by),
    )
    flash("Your suggestion has been submitted for review.", "success")
    return redirect(url_for("user.ruler_detail", person_id=person_id))


@user_bp.route("/dynasties/<int:dynasty_id>/suggest", methods=["GET", "POST"])
@viewer_required
def suggest_dynasty_edit(dynasty_id: int):
    dynasty_rows = execute_query(
        """
        SELECT dynasty_id, name, start_year, end_year, description
        FROM Dynasty
        WHERE dynasty_id = %s
        """,
        (dynasty_id,),
    )
    if not dynasty_rows:
        flash("Dynasty not found.", "error")
        return redirect(url_for("user.dynasties"))
    dynasty = dynasty_rows[0]

    if request.method == "GET":
        current_values = {
            "name": dynasty[1],
            "description": dynasty[4],
            "start_year": dynasty[2],
            "end_year": dynasty[3],
        }
        return render_template(
            "suggest_edit.html",
            entity_type="dynasty",
            entity_id=dynasty_id,
            entity_name=dynasty[1],
            current_values=current_values,
            fields=list(_DYNASTY_SUGGEST_FIELDS.keys()),
            back_url=url_for("user.dynasty_detail", dynasty_id=dynasty_id),
        )

    field_name = (request.form.get("field_name") or "").strip()
    new_value = (request.form.get("new_value") or "").strip()
    reason = (request.form.get("reason") or "").strip() or None
    if field_name not in _DYNASTY_SUGGEST_FIELDS:
        flash("Invalid field selected.", "error")
        return redirect(url_for("user.suggest_dynasty_edit", dynasty_id=dynasty_id))
    if not new_value:
        flash("Please provide a suggested new value.", "error")
        return redirect(url_for("user.suggest_dynasty_edit", dynasty_id=dynasty_id))

    old_value_raw = dynasty[_DYNASTY_SUGGEST_FIELDS[field_name]]
    old_value = str(old_value_raw) if old_value_raw is not None else None
    submitted_by = current_user.username
    execute_query(
        """
        INSERT INTO Edit_Request (entity_type, entity_id, field_name, old_value, new_value, reason, submitted_by, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
        """,
        ("dynasty", dynasty_id, field_name, old_value, new_value, reason, submitted_by),
    )
    flash("Your suggestion has been submitted for review.", "success")
    return redirect(url_for("user.dynasty_detail", dynasty_id=dynasty_id))


@user_bp.route("/wars")
def wars():
    emperor_id = (request.args.get("emperor_id") or "").strip()
    year_start = (request.args.get("year_start") or "").strip()
    year_end = (request.args.get("year_end") or "").strip()
    type_ = (request.args.get("type") or "").strip()
    clauses = ["e.type IN ('war', 'battle')"]
    params = []
    if emperor_id:
        clauses.append("EXISTS (SELECT 1 FROM Person_Event pe2 WHERE pe2.event_id = e.event_id AND pe2.person_id = %s)")
        params.append(int(emperor_id))
    if year_start:
        clauses.append("EXTRACT(YEAR FROM e.event_date) >= %s")
        params.append(int(year_start))
    if year_end:
        clauses.append("EXTRACT(YEAR FROM e.event_date) <= %s")
        params.append(int(year_end))
    if type_ in {"war", "battle"}:
        clauses.append("e.type::text = %s")
        params.append(type_)
    where = "WHERE " + " AND ".join(clauses)
    wars_data = execute_query(
        f"""
        SELECT e.event_id, e.name, e.event_date::text, e.end_date::text, e.location, e.description,
               d.name as dynasty, COUNT(pe.person_id) as participant_count
        FROM Event e
        LEFT JOIN Dynasty d ON d.dynasty_id = e.dynasty_id
        LEFT JOIN Person_Event pe ON pe.event_id = e.event_id
        {where}
        GROUP BY e.event_id, d.name
        ORDER BY e.event_date NULLS LAST
        LIMIT 200
        """,
        tuple(params) if params else None,
    )
    rulers = execute_query("SELECT person_id, full_name FROM Person ORDER BY full_name LIMIT 200")
    return render_template(
        "wars.html",
        wars=wars_data,
        rulers=rulers,
        emperor_id=emperor_id,
        year_start=year_start,
        year_end=year_end,
        type=type_,
    )


@user_bp.route("/wars/<int:event_id>")
def war_detail(event_id: int):
    rows = execute_query(
        """
        SELECT e.event_id, e.name, e.type::text, e.event_date::text, e.end_date::text, e.location,
               e.description, e.dynasty_id, d.name
        FROM Event e
        LEFT JOIN Dynasty d ON d.dynasty_id = e.dynasty_id
        WHERE e.event_id = %s AND e.type IN ('war', 'battle')
        """,
        (event_id,),
    )
    if not rows:
        flash("War/battle not found.", "error")
        return redirect(url_for("user.wars"))
    event = rows[0]
    participants = execute_query(
        """
        SELECT p.person_id, p.full_name, pe.role
        FROM Person_Event pe
        JOIN Person p ON p.person_id = pe.person_id
        WHERE pe.event_id = %s
        ORDER BY p.full_name
        LIMIT 200
        """,
        (event_id,),
    )
    related_battles = []
    if event[7]:
        related_battles = execute_query(
            """
            SELECT e2.event_id, e2.name, e2.event_date::text, e2.end_date::text, e2.location
            FROM Event e2
            WHERE e2.event_id != %s
              AND e2.type = 'battle'
              AND e2.dynasty_id = %s
              AND (
                  (%s::date IS NULL OR e2.end_date IS NULL OR e2.end_date >= %s::date)
                  AND
                  (%s::date IS NULL OR e2.event_date IS NULL OR e2.event_date <= %s::date)
              )
            ORDER BY e2.event_date NULLS LAST
            LIMIT 200
            """,
            (event_id, event[7], event[3], event[3], event[4], event[4]),
        )
    return render_template(
        "war_detail.html",
        war=event,
        participants=participants,
        related_battles=related_battles,
    )


@user_bp.route("/stats")
def stats():
    longest_reigning = execute_query(
        """
        SELECT p.full_name, d.name, p.person_id,
               MAX(COALESCE(r.end_date, CURRENT_DATE) - r.start_date) as reign_days
        FROM Person p
        JOIN Reign r ON r.person_id = p.person_id
        JOIN Dynasty d ON d.dynasty_id = p.dynasty_id
        GROUP BY p.person_id, p.full_name, d.name
        ORDER BY reign_days DESC
        LIMIT 1
        """
    )
    most_wars = execute_query(
        """
        SELECT p.full_name, p.person_id, COUNT(pe.event_id) as war_count
        FROM Person p
        JOIN Person_Event pe ON pe.person_id = p.person_id
        JOIN Event e ON e.event_id = pe.event_id
        WHERE e.type IN ('war', 'battle')
        GROUP BY p.person_id, p.full_name
        ORDER BY war_count DESC
        LIMIT 1
        """
    )
    outcome_counts = execute_query(
        """
        SELECT COALESCE(outcome, 'unknown') as outcome, COUNT(*)
        FROM Event
        WHERE type IN ('war', 'battle')
        GROUP BY COALESCE(outcome, 'unknown')
        ORDER BY outcome
        LIMIT 200
        """
    )
    succession_chain = execute_query(
        """
        SELECT succession_id, predecessor, successor, type, year, dynasty
        FROM vw_succession_chain
        ORDER BY year NULLS LAST
        LIMIT 200
        """
    )
    most_territories = execute_query(
        """
        SELECT d.name, d.dynasty_id, COUNT(dt.territory_id) as territory_count
        FROM Dynasty d
        JOIN Dynasty_Territory dt ON dt.dynasty_id = d.dynasty_id
        GROUP BY d.dynasty_id, d.name
        ORDER BY territory_count DESC
        LIMIT 1
        """
    )
    total_outcomes = sum(int(r[1]) for r in outcome_counts) or 1
    return render_template(
        "stats.html",
        longest_reigning=longest_reigning[0] if longest_reigning else None,
        most_wars=most_wars[0] if most_wars else None,
        outcome_counts=outcome_counts,
        total_outcomes=total_outcomes,
        succession_chain=succession_chain,
        most_territories=most_territories[0] if most_territories else None,
    )


@user_bp.route("/search")
def search():
    q = (request.args.get("q") or "").strip()
    results = []
    if q:
        like = f"%{q}%"
        results = execute_query(
            """
            SELECT * FROM (
                SELECT 'ruler' as entity_type, person_id as entity_id, full_name as label, '' as sub
                FROM Person WHERE full_name ILIKE %s
                UNION ALL
                SELECT 'dynasty', dynasty_id, name, COALESCE(description, '')
                FROM Dynasty WHERE name ILIKE %s
                UNION ALL
                SELECT 'event', event_id, name, COALESCE(location, '')
                FROM Event WHERE name ILIKE %s
                UNION ALL
                SELECT 'territory', territory_id, name, COALESCE(region, '')
                FROM Territory WHERE name ILIKE %s
            ) s
            LIMIT 200
            """,
            (like, like, like, like),
        )
    grouped_results = {"ruler": [], "dynasty": [], "event": [], "territory": []}
    for r in results:
        grouped_results[str(r[0])].append(r)
    return render_template(
        "search.html",
        q=q,
        results=results,
        grouped_results=grouped_results,
        total_count=len(results),
    )