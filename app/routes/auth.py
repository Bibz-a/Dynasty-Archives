from __future__ import annotations

import re
import secrets

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from firebase_admin import auth as firebase_auth
from flask_limiter import Limiter
from flask_limiter.errors import RateLimitExceeded
from flask_limiter.util import get_remote_address
from flask_login import login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from app import User, csrf
from app.db import execute_query
from app.firebase import firebase_app

auth_bp = Blueprint("auth", __name__)
limiter = Limiter(key_func=get_remote_address, default_limits=[])


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""

    if not username or not password:
        flash("Please enter username and password.", "error")
        return redirect(url_for("auth.login"))

    rows = execute_query(
        """
        SELECT user_id, username, password, role, is_active
        FROM User_Account
        WHERE username = %s
        """,
        (username,),
    )
    if not rows:
        flash("Invalid username or password.", "error")
        return redirect(url_for("auth.login"))

    user_id, db_username, db_password, db_role, is_active = rows[0]
    if is_active is False:
        flash("Account is disabled.", "error")
        return redirect(url_for("auth.login"))
    if str(db_password) == "GOOGLE_AUTH":
        flash("This account uses Google Sign-In. Please use the Google button.", "error")
        return redirect(url_for("auth.login"))

    try:
        ok = check_password_hash(str(db_password), password)
    except Exception:
        ok = False

    if not ok:
        flash("Invalid username or password.", "error")
        return redirect(url_for("auth.login"))

    login_user(User(id=int(user_id), username=str(db_username), role=str(db_role)))
    execute_query(
        """
        UPDATE User_Account
        SET last_login = NOW()
        WHERE user_id = %s
        """,
        (int(user_id),),
    )

    if str(db_role) == "admin":
        return redirect(url_for("admin.dashboard"))
    return redirect(url_for("user.home"))


def _generate_unique_google_username(email: str, fallback_name: str | None = None) -> str:
    """Generate a unique username for Google-auth users."""
    local_part = (email.split("@", 1)[0] if "@" in email else "") or ""
    local_part = re.sub(r"[^A-Za-z0-9_]+", "_", local_part).strip("_").lower()
    if not local_part:
        fallback = re.sub(r"[^A-Za-z0-9_]+", "_", (fallback_name or "viewer")).strip("_").lower()
        local_part = fallback or "viewer"
    base = local_part[:46] if len(local_part) > 46 else local_part
    candidate = base
    while execute_query("SELECT user_id FROM User_Account WHERE username = %s", (candidate,)):
        candidate = f"{base}_{secrets.randbelow(9000) + 1000}"
    return candidate


@auth_bp.route("/auth/google-login", methods=["POST"])
@csrf.exempt
def google_login():
    _ = firebase_app
    payload = request.get_json(silent=True) or {}
    id_token = (payload.get("id_token") or "").strip()
    if not id_token:
        return jsonify({"error": "Invalid token"}), 401
    try:
        decoded = firebase_auth.verify_id_token(id_token)
        email = (decoded.get("email") or "").strip().lower()
        if not email:
            return jsonify({"error": "Invalid token"}), 401
        name = (decoded.get("name") or "").strip()
        _uid = (decoded.get("uid") or "").strip()
        rows = execute_query(
            """
            SELECT user_id, username, role, is_active
            FROM User_Account
            WHERE email = %s
            """,
            (email,),
        )
        if rows:
            user_id, username, role, is_active = rows[0]
            if is_active is False:
                return jsonify({"error": "Account disabled"}), 403
        else:
            username = _generate_unique_google_username(email, name)
            inserted = execute_query(
                """
                INSERT INTO User_Account (username, email, password, role, is_active)
                VALUES (%s, %s, 'GOOGLE_AUTH', 'viewer', TRUE)
                RETURNING user_id, username, role
                """,
                (username, email),
            )
            if not inserted:
                return jsonify({"error": "Sign-in failed."}), 500
            user_id, username, role = inserted[0]

        execute_query(
            """
            UPDATE User_Account
            SET last_login = NOW()
            WHERE user_id = %s
            """,
            (int(user_id),),
        )
        login_user(User(id=int(user_id), username=str(username), role=str(role)))
        redirect_to = "/admin" if str(role) == "admin" else "/"
        return jsonify({"success": True, "redirect": redirect_to})
    except Exception:
        return jsonify({"error": "Invalid token"}), 401


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    username = (request.form.get("username") or "").strip()
    email = (request.form.get("email") or "").strip()
    password = request.form.get("password") or ""
    confirm_password = request.form.get("confirm_password") or ""

    if not username or not email or not password or not confirm_password:
        flash("All fields are required.", "error")
        return redirect(url_for("auth.register"))
    if len(username) < 3 or len(username) > 50 or not re.fullmatch(r"[A-Za-z0-9_]+", username):
        flash("Username must be 3-50 characters and contain only letters, numbers, and underscores.", "error")
        return redirect(url_for("auth.register"))
    if "@" not in email:
        flash("Please enter a valid email address.", "error")
        return redirect(url_for("auth.register"))
    if len(password) < 8:
        flash("Password must be at least 8 characters.", "error")
        return redirect(url_for("auth.register"))
    if password != confirm_password:
        flash("Password and confirm password do not match.", "error")
        return redirect(url_for("auth.register"))

    existing = execute_query("SELECT user_id FROM User_Account WHERE username = %s", (username,))
    if existing:
        flash("Username already taken.", "error")
        return redirect(url_for("auth.register"))

    hashed = generate_password_hash(password)
    execute_query(
        """
        INSERT INTO User_Account (username, email, password, role, is_active)
        VALUES (%s, %s, %s, 'viewer', TRUE)
        """,
        (username, email, hashed),
    )
    flash("Account created! You can now log in.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/logout")
def logout():
    logout_user()
    flash("Logged out.", "success")
    return redirect(url_for("user.home"))


@auth_bp.errorhandler(RateLimitExceeded)
def login_rate_limited(_e):
    flash("Too many login attempts. Please wait a minute and try again.", "error")
    return redirect(url_for("auth.login"))

