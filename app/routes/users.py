"""
User management routes (Admin only).
"""
from flask import Blueprint, request
from app.middleware.auth import require_admin
from app.services import user_service
from app.utils.response import api_success, api_error
from app.utils.validators import int_or_none

bp = Blueprint("users", __name__, url_prefix="/users")


@bp.route("", methods=["GET"])
@require_admin
def list_users():
    """GET /users - List all users (Admin)."""
    role = request.args.get("role")
    data, err = user_service.list_users(role=role)
    if err:
        return api_error(err, 500)
    return api_success({"users": data, "count": len(data)})


@bp.route("/<int:user_id>", methods=["GET"])
@require_admin
def get_user(user_id):
    """GET /users/{id} - Get user by id (Admin)."""
    data, err = user_service.get_user(user_id)
    if err:
        return api_error(err, 404)
    return api_success(data)


@bp.route("/<int:user_id>", methods=["PUT"])
@require_admin
def update_user(user_id):
    """UPDATE /users/{id} - Update user (Admin)."""
    data = request.get_json(silent=True) or {}
    allowed = {"full_name", "email", "password", "role"}
    payload = {k: v for k, v in data.items() if k in allowed}
    if "role" in payload and payload["role"] not in ("ADMIN", "EMPLOYEE"):
        return api_error("role must be ADMIN or EMPLOYEE", 400)
    updated, err = user_service.update_user(
        user_id,
        full_name=payload.get("full_name"),
        email=payload.get("email"),
        password=payload.get("password"),
        role=payload.get("role"),
    )
    if err:
        return api_error(err, 400 if "role" in err or "password" in err else 500)
    return api_success(updated, message="User updated")


@bp.route("/<int:user_id>", methods=["DELETE"])
@require_admin
def delete_user(user_id):
    """DELETE /users/{id} - Delete user (Admin)."""
    ok, err = user_service.delete_user(user_id)
    if err:
        return api_error(err, 404 if "not found" in err else 500)
    return api_success(None, message="User deleted")
