"""
Supabase client initialization.
Reads credentials from environment variables and exposes a single
get_supabase_client() helper used by the backup route.
"""
from __future__ import annotations

import os

from supabase import Client, create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
SUPABASE_BACKUP_BUCKET = os.environ.get("SUPABASE_BACKUP_BUCKET", "dynasty-backups")

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL environment variable is not set.")
if not SUPABASE_SERVICE_KEY:
    raise RuntimeError("SUPABASE_SERVICE_KEY environment variable is not set.")

_client: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def get_supabase_client() -> Client:
    """Returns the initialized Supabase client."""
    return _client

