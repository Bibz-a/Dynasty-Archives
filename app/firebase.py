from __future__ import annotations

import base64
import os
from datetime import datetime

import firebase_admin
from firebase_admin import credentials, db


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
service_account_path = os.environ.get(
    "FIREBASE_SERVICE_ACCOUNT_JSON", "secrets/serviceAccountKey.json"
)
if not os.path.isabs(service_account_path):
    service_account_path = os.path.join(BASE_DIR, service_account_path)
if not os.path.exists(service_account_path):
    raise RuntimeError(f"Firebase service account file not found at: {service_account_path}")

FIREBASE_DATABASE_URL = os.environ.get("FIREBASE_DATABASE_URL", "")
if not FIREBASE_DATABASE_URL:
    raise RuntimeError("FIREBASE_DATABASE_URL environment variable is not set.")


def _create_firebase_app():
    if firebase_admin._apps:
        return firebase_admin.get_app()

    cred = credentials.Certificate(service_account_path)
    return firebase_admin.initialize_app(
        cred,
        {
            "databaseURL": FIREBASE_DATABASE_URL,
        },
    )


firebase_app = _create_firebase_app()


def write_backup_to_realtime_db(filename: str, sql_content: str) -> str:
    """
    Writes a SQL backup string to Firebase Realtime Database under /backups/{filename}.
    SQL content is base64-encoded to avoid JSON escaping corruption.
    Returns the database path as a reference string.
    Raises RuntimeError on failure.
    """
    try:
        encoded = base64.b64encode(sql_content.encode("utf-8")).decode("utf-8")
        key = filename.replace(".", "_").replace("-", "_")
        ref = db.reference(f"/backups/{key}")
        ref.set(
            {
                "filename": filename,
                "content_b64": encoded,
                "created_at": datetime.utcnow().isoformat(),
                "size_kb": round(len(sql_content.encode("utf-8")) / 1024, 2),
            }
        )
        return f"{FIREBASE_DATABASE_URL}/backups/{key}.json"
    except Exception as e:
        raise RuntimeError(f"Firebase Realtime DB write failed: {e}")

