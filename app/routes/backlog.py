"""Backlog: Admin create; both can read/update/delete if project access."""
from flask import Blueprint, request, g
from app.middleware.auth import require_admin, require_auth_admin_or_employee
from app.services import backlog_service
from app.utils.response import api_success, api_error
from app.utils.validators import required_keys, int_or_none

bp = Blueprint("backlog", __name__, url_prefix="/projects")


def _current_employee_id():
    return None if g.current_user.get("role") == "ADMIN" else g.current_user.get("user_id")


@bp.route("/<int:project_id>/backlog", methods=["POST"])
@require_admin
def create_backlog(project_id):
    data = request.get_json(silent=True) or {}
    err = required_keys(data, ["title"])
    if err:
        return api_error(err, 400)
    priority = int_or_none(data.get("priority"))
    if priority is None:
        priority = 0
    row, err = backlog_service.create_backlog_item(project_id, data.get("title"), data.get("description") or "", priority)
    if err:
        return api_error(err, 400 if "not found" in err else 500)
    return api_success(row, message="Backlog item created", status=201)


@bp.route("/<int:project_id>/backlog", methods=["GET"])
@require_auth_admin_or_employee
def list_backlog(project_id):
    data, err = backlog_service.list_backlog(project_id, _current_employee_id())
    if err:
        return api_error(err, 404 if "not found" in err else 500)
    return api_success({"backlog_items": data, "count": len(data)})


# Backlog by id (update/delete)
backlog_id_bp = Blueprint("backlog_id", __name__, url_prefix="/backlog")


@backlog_id_bp.route("/<int:backlog_item_id>", methods=["PUT"])
@require_auth_admin_or_employee
def update_backlog(backlog_item_id):
    data = request.get_json(silent=True) or {}
    payload = {k: v for k, v in data.items() if k in ("title", "description", "priority")}
    if "priority" in payload and payload["priority"] is not None:
        p = int_or_none(payload["priority"])
        if p is None:
            return api_error("priority must be an integer", 400)
        payload["priority"] = p
    if not payload:
        return api_error("No valid fields to update", 400)
    row, err = backlog_service.update_backlog_item(backlog_item_id, **payload)
    if err:
        return api_error(err, 404 if "not found" in err else 500)
    return api_success(row, message="Backlog item updated")


@backlog_id_bp.route("/<int:backlog_item_id>", methods=["DELETE"])
@require_admin
def delete_backlog(backlog_item_id):
    ok, err = backlog_service.delete_backlog_item(backlog_item_id)
    if err:
        return api_error(err, 404 if "not found" in err else 500)
    return api_success(None, message="Backlog item deleted")
