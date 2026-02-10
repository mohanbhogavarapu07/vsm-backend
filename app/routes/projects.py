"""
Projects and assignments. Admin: full CRUD. Employee: only assigned projects.
"""
from flask import Blueprint, request, g
from app.middleware.auth import require_admin, require_auth_admin_or_employee
from app.services import project_service
from app.utils.response import api_success, api_error
from app.utils.validators import required_keys, int_or_none

bp = Blueprint("projects", __name__, url_prefix="/projects")


def _current_employee_id():
    """None if Admin, else user_id (Employee)."""
    if g.current_user.get("role") == "ADMIN":
        return None
    return g.current_user.get("user_id")


@bp.route("", methods=["POST"])
@require_admin
def create_project():
    """POST /projects - Admin only."""
    data = request.get_json(silent=True) or {}
    err = required_keys(data, ["project_name", "created_by_admin_id"])
    if err:
        return api_error(err, 400)
    admin_id = int_or_none(data.get("created_by_admin_id"))
    if admin_id is None:
        return api_error("created_by_admin_id must be a valid integer", 400)
    row, err = project_service.create_project(
        data.get("project_name"),
        admin_id,
        description=data.get("description"),
        start_date=data.get("start_date"),
        end_date=data.get("end_date"),
    )
    if err:
        return api_error(err, 400 if "not found" in err else 500)
    return api_success(row, message="Project created", status=201)


@bp.route("", methods=["GET"])
@require_auth_admin_or_employee
def list_projects():
    """GET /projects - Admin: all; Employee: only assigned."""
    data, err = project_service.list_projects(employee_id=_current_employee_id())
    if err:
        return api_error(err, 500)
    return api_success({"projects": data, "count": len(data)})


@bp.route("/<int:project_id>", methods=["GET"])
@require_auth_admin_or_employee
def get_project(project_id):
    data, err = project_service.get_project(project_id, employee_id=_current_employee_id())
    if err:
        return api_error(err, 404)
    return api_success(data)


@bp.route("/<int:project_id>", methods=["PUT"])
@require_admin
def update_project(project_id):
    data = request.get_json(silent=True) or {}
    payload = {k: v for k, v in data.items() if k in ("project_name", "description", "start_date", "end_date")}
    if not payload:
        return api_error("No valid fields to update", 400)
    row, err = project_service.update_project(project_id, **payload)
    if err:
        return api_error(err, 400 if "not found" in err else 500)
    return api_success(row, message="Project updated")


@bp.route("/<int:project_id>", methods=["DELETE"])
@require_admin
def delete_project(project_id):
    ok, err = project_service.delete_project(project_id)
    if err:
        return api_error(err, 404 if "not found" in err else 500)
    return api_success(None, message="Project deleted")


# --- Assignments (Admin) ---
@bp.route("/<int:project_id>/assign", methods=["POST"])
@require_admin
def assign(project_id):
    """
    Assign employee(s) to project. Accepts:
    - {"employee_id": 1} - single employee
    - {"employee_ids": [1, 2, 3]} - multiple employees
    """
    data = request.get_json(silent=True) or {}
    employee_ids_raw = data.get("employee_ids")
    employee_id_single = int_or_none(data.get("employee_id"))

    if employee_ids_raw is not None:
        # Multiple: employee_ids must be list of integers
        if not isinstance(employee_ids_raw, list):
            return api_error("employee_ids must be an array of integers, e.g. [1, 2, 3]", 400)
        ids = [int_or_none(x) for x in employee_ids_raw]
        if any(x is None for x in ids):
            return api_error("employee_ids must contain only valid integers", 400)
        ids = [x for x in ids if x is not None]
        if not ids:
            return api_error("employee_ids must not be empty", 400)
        rows, err = project_service.assign_employees(project_id, ids)
        if err and not rows:
            return api_error(err, 400 if "not found" in err or "already" in err else 500)
        return api_success(
            {"assignments": rows, "count": len(rows)},
            message=f"{len(rows)} employee(s) assigned" + (" (some skipped - already assigned)" if err else ""),
            status=201,
        )
    elif employee_id_single is not None:
        # Single: employee_id
        row, err = project_service.assign_employee(project_id, employee_id_single)
        if err:
            return api_error(err, 400 if "not found" in err or "already" in err else 500)
        return api_success(row, message="Employee assigned", status=201)
    else:
        return api_error("Provide employee_id (single) or employee_ids (array). Example: {\"employee_ids\": [1, 2, 3]}", 400)


@bp.route("/<int:project_id>/members", methods=["GET"])
@require_admin
def list_members(project_id):
    data, err = project_service.list_members(project_id)
    if err:
        return api_error(err, 500)
    return api_success({"members": data, "count": len(data)})


@bp.route("/<int:project_id>/members/<int:user_id>", methods=["DELETE"])
@require_admin
def remove_member(project_id, user_id):
    ok, err = project_service.remove_member(project_id, user_id)
    if err:
        return api_error(err, 404 if "not found" in err else 500)
    return api_success(None, message="Member removed")
