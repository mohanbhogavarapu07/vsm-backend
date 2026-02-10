"""Sprints: Admin create/update/delete; both can list/get if project access."""
from flask import Blueprint, request, g
from app.middleware.auth import require_admin, require_auth_admin_or_employee
from app.services import sprint_service
from app.utils.response import api_success, api_error
from app.utils.validators import required_keys

bp = Blueprint("sprints", __name__, url_prefix="/projects")


def _current_employee_id():
    return None if g.current_user.get("role") == "ADMIN" else g.current_user.get("user_id")


@bp.route("/<int:project_id>/sprints", methods=["POST"])
@require_admin
def create_sprint(project_id):
    data = request.get_json(silent=True) or {}
    err = required_keys(data, ["sprint_name"])
    if err:
        return api_error(err, 400)
    status = (data.get("status") or "PLANNED").upper()
    if status not in ("PLANNED", "ACTIVE", "COMPLETED"):
        return api_error("status must be PLANNED, ACTIVE, or COMPLETED", 400)
    row, err = sprint_service.create_sprint(
        project_id,
        data.get("sprint_name"),
        start_date=data.get("start_date"),
        end_date=data.get("end_date"),
        status=status,
    )
    if err:
        return api_error(err, 400 if "not found" in err else 500)
    return api_success(row, message="Sprint created", status=201)


@bp.route("/<int:project_id>/sprints", methods=["GET"])
@require_auth_admin_or_employee
def list_sprints(project_id):
    data, err = sprint_service.list_sprints(project_id, _current_employee_id())
    if err:
        return api_error(err, 404 if "not found" in err else 500)
    return api_success({"sprints": data, "count": len(data)})


# Sprint by id (get/update/delete)
sprint_id_bp = Blueprint("sprint_id", __name__, url_prefix="/sprints")


@sprint_id_bp.route("/<int:sprint_id>", methods=["GET"])
@require_auth_admin_or_employee
def get_sprint(sprint_id):
    row, err = sprint_service.get_sprint(sprint_id, _current_employee_id())
    if err:
        return api_error(err, 404)
    return api_success(row)


@sprint_id_bp.route("/<int:sprint_id>", methods=["PUT"])
@require_admin
def update_sprint(sprint_id):
    data = request.get_json(silent=True) or {}
    payload = {k: v for k, v in data.items() if k in ("sprint_name", "start_date", "end_date", "status")}
    if "status" in payload:
        payload["status"] = (payload["status"] or "").upper()
        if payload["status"] not in ("PLANNED", "ACTIVE", "COMPLETED"):
            return api_error("status must be PLANNED, ACTIVE, or COMPLETED", 400)
    if not payload:
        return api_error("No valid fields to update", 400)
    row, err = sprint_service.update_sprint(sprint_id, **payload)
    if err:
        return api_error(err, 404 if "not found" in err else 500)
    return api_success(row, message="Sprint updated")


@sprint_id_bp.route("/<int:sprint_id>", methods=["DELETE"])
@require_admin
def delete_sprint(sprint_id):
    ok, err = sprint_service.delete_sprint(sprint_id)
    if err:
        return api_error(err, 404 if "not found" in err else 500)
    return api_success(None, message="Sprint deleted")
