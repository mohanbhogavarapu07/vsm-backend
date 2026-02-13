"""
Auth routes: register, login, me.
"""
import json
from flask import Blueprint, request, g
from app.middleware.auth import require_auth, create_token
from app.services.auth_service import register, login, get_user_by_id
from app.utils.response import api_success, api_error
from app.utils.validators import required_keys

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.route("/register", methods=["POST"])
def register_route():
    """POST /auth/register - Create new user."""
    data = request.get_json(silent=True) or {}
    err = required_keys(data, ["full_name", "email", "password", "role"])
    if err:
        return api_error(err, 400)
    user, err = register(
        data.get("full_name"),
        data.get("email"),
        data.get("password"),
        (data.get("role") or "").upper(),
    )
    if err:
        return api_error(err, 400 if "already exists" in err else 500)
    token = create_token(user["user_id"], user["role"], user["email"])
    return api_success({"user": user, "token": token}, message="Registered successfully", status=201)


def _get_login_data():
    """
    Get email and password from request. Accepts:
    - JSON body: {"email": "...", "password": "..."}
    - Form data: email=...&password=...
    - Raw body with JSON (even without Content-Type)
    - Also accepts "username" as alias for "email"
    Returns (email, password) or (None, None) with error message.
    """
    data = request.get_json(silent=True)
    if data is None and request.data:
        try:
            data = json.loads(request.data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
    if data is None:
        data = dict(request.form) if request.form else {}
    if not data:
        return None, None, "Request body is required. Send JSON: {\"email\": \"...\", \"password\": \"...\"} or form data with email and password."

    def _val(k):
        v = data.get(k)
        if isinstance(v, list):
            return v[0] if v else None
        return v

    email = _val("email") or _val("username")
    password = _val("password")
    if not email or (isinstance(email, str) and not email.strip()):
        return None, None, "Missing or empty 'email' (or 'username')."
    if not password or (isinstance(password, str) and not password.strip()):
        return None, None, "Missing or empty 'password'."
    return str(email).strip(), str(password), None


@bp.route("/login", methods=["POST"])
def login_route():
    """POST /auth/login - Authenticate and return JWT."""
    email, password, err = _get_login_data()
    if err:
        return api_error(err, 400)
    user, err = login(email, password)
    if err:
        return api_error(err, 401)
    token = create_token(user["user_id"], user["role"], user["email"])
    return api_success({"user": user, "token": token}, message="Login successful")


@bp.route("/me", methods=["GET"])
@require_auth
def me():
    """GET /auth/me - Current user from JWT."""
    user, err = get_user_by_id(g.current_user["user_id"])
    if err:
        return api_error(err, 404)
    return api_success(user, message="OK")


@bp.route("/refresh", methods=["POST", "OPTIONS"])
@require_auth
def refresh():
    """POST /auth/refresh - Refresh JWT token with current user data from DB."""
    user, err = get_user_by_id(g.current_user["user_id"])
    if err:
        return api_error(err, 404)
    # Create new token with current role from DB
    token = create_token(user["user_id"], user["role"], user["email"])
    return api_success({"user": user, "token": token}, message="Token refreshed")
