"""
JWT authentication and role-based access control.
- require_auth: any authenticated user (sets g.current_user)
- require_admin: only ADMIN
- require_employee: only EMPLOYEE (or admin for some routes we allow both)
"""
import jwt
from datetime import datetime, timedelta
from functools import wraps
from flask import request, g, current_app

from app.utils.response import api_error


def _get_token_from_request(auth_header: str = "", x_access_token: str = "") -> str | None:
    """Extract JWT from Authorization or X-Access-Token. Accepts Bearer (case-insensitive)."""
    auth = (auth_header or "").strip()
    if auth:
        parts = auth.split(None, 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1].strip()
    return (x_access_token or "").strip() or None


def _get_token() -> str | None:
    """Extract JWT from request headers."""
    return _get_token_from_request(
        request.headers.get("Authorization", ""),
        request.headers.get("X-Access-Token", ""),
    )


def decode_token(token: str):
    """
    Decode JWT. Returns (payload, None) or (None, error_hint).
    error_hint: "expired" | "malformed" | "signature_invalid" | "decode_error" | "algorithm_invalid"
    """
    if not token or not isinstance(token, str):
        return None, "malformed"
    # Strip surrounding quotes (client may send JSON-stringified token)
    token = token.strip().strip('"\'')
    if token.count(".") != 2:
        return None, "malformed"
    secret = current_app.config["JWT_SECRET_KEY"]
    algo = current_app.config["JWT_ALGORITHM"]
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[algo],
        )
        return payload, None
    except jwt.ExpiredSignatureError:
        return None, "expired"
    except jwt.InvalidSignatureError:
        return None, "signature_invalid"
    except jwt.DecodeError:
        return None, "decode_error"
    except jwt.InvalidAlgorithmError:
        return None, "algorithm_invalid"
    except jwt.InvalidTokenError:
        return None, "invalid"


def require_auth(f):
    """Decorator: require valid JWT; set g.current_user = { user_id, role, email }."""

    @wraps(f)
    def wrapped(*args, **kwargs):
        token = _get_token()
        if not token:
            return api_error("Missing token. Add header: Authorization: Bearer <token>", 401)
        payload, err_hint = decode_token(token)
        if not payload or "sub" not in payload:
            msg = "Token has expired. Log in again." if err_hint == "expired" else "Invalid or expired token"
            return api_error(msg, 401)
        g.current_user = {
            "user_id": int(payload["sub"]),
            "role": payload.get("role", "EMPLOYEE"),
            "email": payload.get("email", ""),
        }
        return f(*args, **kwargs)

    return wrapped


def require_admin(f):
    """Decorator: require authenticated user with role ADMIN."""

    @wraps(f)
    @require_auth
    def wrapped(*args, **kwargs):
        if g.current_user.get("role") != "ADMIN":
            return api_error("Admin access required", 403)
        return f(*args, **kwargs)

    return wrapped


def require_employee(f):
    """Decorator: require authenticated user with role EMPLOYEE (used for employee-only endpoints)."""

    @wraps(f)
    @require_auth
    def wrapped(*args, **kwargs):
        if g.current_user.get("role") != "EMPLOYEE":
            return api_error("Employee access required", 403)
        return f(*args, **kwargs)

    return wrapped


def require_auth_admin_or_employee(f):
    """Decorator: require authenticated user (ADMIN or EMPLOYEE). Used for shared endpoints like GET /projects."""

    @wraps(f)
    @require_auth
    def wrapped(*args, **kwargs):
        if g.current_user.get("role") not in ("ADMIN", "EMPLOYEE"):
            return api_error("Access denied", 403)
        return f(*args, **kwargs)

    return wrapped


def create_token(user_id: int, role: str, email: str) -> str:
    """Generate JWT for user. Always returns a string."""
    exp_hours = current_app.config.get("JWT_EXPIRATION_HOURS", 24)
    payload = {
        "sub": str(user_id),  # JWT spec requires sub to be a string
        "role": role,
        "email": email,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=exp_hours),
    }
    encoded = jwt.encode(
        payload,
        current_app.config["JWT_SECRET_KEY"],
        algorithm=current_app.config["JWT_ALGORITHM"],
    )
    return encoded.decode("utf-8") if isinstance(encoded, bytes) else encoded