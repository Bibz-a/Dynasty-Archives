from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
import json

from flask import Flask, g, send_from_directory
from flask_login import LoginManager
from flask_login import current_user
from flask_wtf.csrf import CSRFProtect

from app.db import execute_query
from config import Config

csrf = CSRFProtect()


@dataclass(frozen=True)
class User:
    id: int
    username: str
    role: str

    @property
    def is_authenticated(self) -> bool:  # Flask-Login expects this attribute
        return True

    @property
    def is_active(self) -> bool:  # Flask-Login expects this attribute
        return True

    @property
    def is_anonymous(self) -> bool:  # Flask-Login expects this attribute
        return False

    def get_id(self) -> str:
        return str(self.id)


def create_app() -> Flask:
    def _pick_query_preview(query_log) -> str:
        """Pick the most relevant query preview for debug toast."""
        if not query_log:
            return ""
        previews = [q.get("preview", "") if isinstance(q, dict) else str(q) for q in query_log]
        lowered = [p.lower() for p in previews]

        # Prefer user-facing filtered selects over framework/admin helper queries.
        for idx in range(len(previews) - 1, -1, -1):
            p = lowered[idx]
            if (
                "select" in p
                and " where " in p
                and "edit_request" not in p
                and "audit_log" not in p
            ):
                return previews[idx]
        return previews[-1]

    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = Config.SECRET_KEY
    csrf.init_app(app)
    app.config["FIREBASE_API_KEY"] = (os.getenv("FIREBASE_API_KEY") or "").strip()
    app.config["FIREBASE_AUTH_DOMAIN"] = (os.getenv("FIREBASE_AUTH_DOMAIN") or "").strip()
    app.config["FIREBASE_PROJECT_ID"] = (os.getenv("FIREBASE_PROJECT_ID") or "").strip()
    app.config["FIREBASE_DATABASE_URL"] = (os.getenv("FIREBASE_DATABASE_URL") or "").strip()
    if (
        not app.config["FIREBASE_API_KEY"]
        or not app.config["FIREBASE_AUTH_DOMAIN"]
        or not app.config["FIREBASE_PROJECT_ID"]
        or not app.config["FIREBASE_DATABASE_URL"]
    ):
        raise RuntimeError("FIREBASE_API_KEY, FIREBASE_AUTH_DOMAIN, FIREBASE_PROJECT_ID, and FIREBASE_DATABASE_URL must be set.")
    from app.supabase_client import get_supabase_client
    _ = get_supabase_client()

    @app.after_request
    def inject_query_header(response):
        queries = getattr(g, "query_log", [])
        if queries:
            response.headers["X-Last-Query"] = json.dumps(_pick_query_preview(queries))
        return response

    @app.template_filter("relative_time")
    def relative_time(value):
        """Render a compact relative-time string for dashboard history rows."""
        if value is None:
            return ""

        dt = value
        if isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return value

        if not isinstance(dt, datetime):
            return str(value)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = now - dt
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return "just now"
        if seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        if seconds < 86400:
            hours = seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        days = seconds // 86400
        return f"{days} day{'s' if days != 1 else ''} ago"

    @app.context_processor
    def inject_admin_pending_edit_count():
        if not getattr(current_user, "is_authenticated", False) or getattr(current_user, "role", None) != "admin":
            return {"pending_edit_requests_count": 0}
        try:
            pending = execute_query("SELECT COUNT(*) FROM Edit_Request WHERE status = 'pending'")
            return {"pending_edit_requests_count": int(pending[0][0]) if pending else 0}
        except Exception:
            return {"pending_edit_requests_count": 0}

    @app.context_processor
    def inject_last_query():
        qlog = getattr(g, "query_log", None)
        return {"last_query": _pick_query_preview(qlog)}

    login_manager = LoginManager()
    login_manager.login_view = "admin.login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str) -> User | None:
        try:
            uid = int(user_id)
        except (TypeError, ValueError):
            return None

        rows = execute_query(
            """
            SELECT user_id, username, role, is_active
            FROM User_Account
            WHERE user_id = %s
            """,
            (uid,),
        )
        if not rows:
            return None
        db_user_id, db_username, db_role, is_active = rows[0]
        if is_active is False:
            return None
        return User(id=int(db_user_id), username=str(db_username), role=str(db_role))

    from app.routes.user import user_bp
    from app.routes.admin import admin_bp
    from app.routes.auth import auth_bp, limiter

    app.register_blueprint(user_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(auth_bp)
    limiter.init_app(app)

    # Serve project-level images folder at /images/<filename>
    @app.get("/images/<path:filename>")
    def project_images(filename: str):
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        images_dir = os.path.join(project_root, "images")
        return send_from_directory(images_dir, filename)

    return app