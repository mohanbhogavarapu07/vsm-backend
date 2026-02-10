"""
Authentication: register, login, and current user logic.

Passwords are hashed before storage. Login uses check_password_hash to verify
the entered password against the stored hash (no decryption - hashes are one-way).
"""
from app.services.db import get_supabase, one, exists
from werkzeug.security import generate_password_hash, check_password_hash
from typing import Tuple, Optional, Any


def register(full_name: str, email: str, password: str, role: str) -> Tuple[Optional[dict], Optional[str]]:
    """
    Register a new user. Returns (user_dict, None) or (None, error_message).
    Role must be ADMIN or EMPLOYEE.
    """
    if role not in ("ADMIN", "EMPLOYEE"):
        return None, "role must be ADMIN or EMPLOYEE"
    email = (email or "").strip()
    if not email:
        return None, "email is required"
    if not password or len(password) < 6:
        return None, "password must be at least 6 characters"
    sb = get_supabase()
    # Check duplicate email
    try:
        r = sb.table("users").select("user_id").eq("email", email).limit(1).execute()
        if getattr(r, "data", []) and len(r.data) > 0:
            return None, "A user with this email already exists"
    except Exception as e:
        return None, str(e)
    password_hash = generate_password_hash(password)
    try:
        r = sb.table("users").insert({
            "full_name": (full_name or "").strip(),
            "email": email,
            "password_hash": password_hash,
            "role": role,
        }).execute()
        row, err = one(r, "User")
        if err:
            return None, err
        # Don't return password_hash to client
        if row:
            row = {k: v for k, v in row.items() if k != "password_hash"}
        return row, None
    except Exception as e:
        return None, str(e)


def login(email: str, password: str) -> Tuple[Optional[dict], Optional[str]]:
    """
    Authenticate user. Returns (user_dict_with_token, None) or (None, error_message).
    """
    email = (email or "").strip()
    if not email or not password:
        return None, "email and password are required"
    sb = get_supabase()
    try:
        r = sb.table("users").select("*").eq("email", email).limit(1).execute()
        row, err = one(r, "User")
        if err:
            return None, "Invalid email or password"
        # Verify password: try hashed first, then fallback for legacy plaintext
        stored = (row.get("password_hash") or "").strip()
        if not stored:
            return None, "Invalid email or password"
        valid = False
        if stored.startswith(("pbkdf2:", "scrypt:", "sha256$")):
            try:
                valid = check_password_hash(stored, password)
            except (ValueError, TypeError):
                valid = stored == password
        else:
            # Legacy plaintext or unknown format
            valid = stored == password
        if not valid:
            return None, "Invalid email or password"
        user = {k: v for k, v in row.items() if k != "password_hash"}
        return user, None
    except Exception as e:
        return None, str(e)


def get_user_by_id(user_id: int) -> Tuple[Optional[dict], Optional[str]]:
    """Get user by id (without password_hash)."""
    sb = get_supabase()
    try:
        r = sb.table("users").select("user_id, full_name, email, role, created_at, updated_at").eq("user_id", user_id).limit(1).execute()
        row, err = one(r, "User")
        if err:
            return None, err
        return row, None
    except Exception as e:
        return None, str(e)
