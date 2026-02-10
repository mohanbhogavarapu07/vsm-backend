"""
Supabase client singleton and DB helpers.
"""
from flask import current_app
from supabase import create_client, Client
from typing import Optional, List, Any

_supabase: Optional[Client] = None


def get_supabase() -> Client:
    """Get Supabase client (requires app context)."""
    global _supabase
    if _supabase is None:
        url = current_app.config.get("SUPABASE_URL")
        key = current_app.config.get("SUPABASE_KEY")
        if not url or not key:
            raise RuntimeError("Supabase is not configured (SUPABASE_URL / SUPABASE_KEY).")
        _supabase = create_client(url, key)
    return _supabase


def one(resp: Any, name: str = "Resource") -> tuple:
    """Get single row from Supabase response. Returns (row, None) or (None, error_message)."""
    data = getattr(resp, "data", None) or []
    if not data:
        return None, f"{name} not found"
    return data[0], None


def exists(sb: Client, table: str, column: str, value: Any) -> bool:
    """Return True if a row exists."""
    try:
        r = sb.table(table).select(column).eq(column, value).limit(1).execute()
        return len(getattr(r, "data", []) or []) > 0
    except Exception:
        return False
