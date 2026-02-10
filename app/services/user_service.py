"""
User CRUD (Admin only in routes).

Passwords are hashed before storage using werkzeug.security.
"""
from app.services.db import get_supabase, one, exists
from werkzeug.security import generate_password_hash
from typing import Tuple, Optional, List


def list_users(role: Optional[str] = None) -> Tuple[List[dict], Optional[str]]:
    """List all users; optional filter by role."""
    sb = get_supabase()
    try:
        q = sb.table("users").select("user_id, full_name, email, role, created_at, updated_at").order("user_id")
        if role and role in ("ADMIN", "EMPLOYEE"):
            q = q.eq("role", role)
        r = q.execute()
        data = getattr(r, "data", []) or []
        return data, None
    except Exception as e:
        return [], str(e)


def get_user(user_id: int) -> Tuple[Optional[dict], Optional[str]]:
    """Get user by id (no password)."""
    sb = get_supabase()
    try:
        r = sb.table("users").select("user_id, full_name, email, role, created_at, updated_at").eq("user_id", user_id).limit(1).execute()
        row, err = one(r, "User")
        if err:
            return None, err
        return row, None
    except Exception as e:
        return None, str(e)


def update_user(user_id: int, full_name: Optional[str] = None, email: Optional[str] = None, password: Optional[str] = None, role: Optional[str] = None) -> Tuple[Optional[dict], Optional[str]]:
    """Update user. Only provided fields are updated."""
    if role is not None and role not in ("ADMIN", "EMPLOYEE"):
        return None, "role must be ADMIN or EMPLOYEE"
    sb = get_supabase()
    payload = {}
    if full_name is not None:
        payload["full_name"] = full_name.strip()
    if email is not None:
        payload["email"] = email.strip()
    if role is not None:
        payload["role"] = role
    if password is not None:
        if len(password) < 6:
            return None, "password must be at least 6 characters"
        payload["password_hash"] = generate_password_hash(password)
    if not payload:
        return get_user(user_id)
    try:
        r = sb.table("users").update(payload).eq("user_id", user_id).execute()
        row, err = one(r, "User")
        if err:
            return None, err
        return {k: v for k, v in row.items() if k != "password_hash"}, None
    except Exception as e:
        return None, str(e)


def delete_user(user_id: int) -> Tuple[bool, Optional[str]]:
    """Delete user. Returns (True, None) or (False, error)."""
    sb = get_supabase()
    try:
        r = sb.table("users").delete().eq("user_id", user_id).execute()
        data = getattr(r, "data", []) or []
        if not data:
            return False, "User not found"
        return True, None
    except Exception as e:
        return False, str(e)
