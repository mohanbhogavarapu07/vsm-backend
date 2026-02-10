"""Tasks: Admin create/delete; Employee can update own task status."""
from flask import Blueprint, request, g
from app.middleware.auth import require_admin, require_auth_admin_or_employee
from app.services import task_service
from app.services.db import get_supabase
from app.services.project_service import employee_can_access_project
from app.utils.response import api_success, api_error
from app.utils.validators import required_keys, int_or_none

# Tasks under sprints
bp = Blueprint("sprint_tasks", __name__, url_prefix="/sprints")


def _current_employee_id():
    return None if g.current_user.get("role") == "ADMIN" else g.current_user.get("user_id")


@bp.route("/<int:sprint_id>/tasks", methods=["POST"])
@require_admin
def create_task(sprint_id):
    data = request.get_json(silent=True) or {}
    err = required_keys(data, ["title"])
    if err:
        return api_error(err, 400)
    status = (data.get("status") or "TODO").upper().replace("-", "_")
    if status not in ("TODO", "IN_PROGRESS", "DONE"):
        return api_error("status must be TODO, IN_PROGRESS, or DONE", 400)
    assigned = int_or_none(data.get("assigned_to_user_id"))
    row, err = task_service.create_task(
        sprint_id,
        data.get("title"),
        description=data.get("description") or "",
        status=status,
        assigned_to_user_id=assigned,
    )
    if err:
        return api_error(err, 400 if "not found" in err else 500)
    return api_success(row, message="Task created", status=201)


@bp.route("/<int:sprint_id>/tasks", methods=["GET"])
@require_auth_admin_or_employee
def list_tasks_sprint(sprint_id):
    sb = get_supabase()
    # Employee: only if they have a task in this sprint or we allow viewing sprint tasks if they have project access
    emp_id = _current_employee_id()
    if emp_id is not None:
        # Check sprint belongs to a project they're in
        sprint_row = sb.table("sprints").select("project_id").eq("sprint_id", sprint_id).limit(1).execute()
        if not (getattr(sprint_row, "data", []) or []):
            return api_error("Sprint not found", 404)
        if not employee_can_access_project(sb, sprint_row.data[0]["project_id"], emp_id):
            return api_error("Sprint not found", 404)
    data, err = task_service.list_tasks_for_sprint(sprint_id, emp_id, sb)
    if err:
        return api_error(err, 500)
    return api_success({"tasks": data, "count": len(data)})


# Tasks by id
tasks_bp = Blueprint("tasks", __name__, url_prefix="/tasks")


@tasks_bp.route("", methods=["GET"])
@require_auth_admin_or_employee
def list_tasks():
    """GET /tasks - Admin: all; Employee: only assigned."""
    data, err = task_service.list_all_tasks(_current_employee_id())
    if err:
        return api_error(err, 500)
    return api_success({"tasks": data, "count": len(data)})


@tasks_bp.route("/<int:task_id>", methods=["GET"])
@require_auth_admin_or_employee
def get_task(task_id):
    row, err = task_service.get_task(task_id, _current_employee_id())
    if err:
        return api_error(err, 404)
    return api_success(row)


@tasks_bp.route("/<int:task_id>", methods=["PUT"])
@require_auth_admin_or_employee
def update_task(task_id):
    """Employee can only update own tasks; Admin can update any."""
    data = request.get_json(silent=True) or {}
    emp_id = _current_employee_id()
    payload = {k: v for k, v in data.items() if k in ("title", "description", "status", "assigned_to_user_id")}
    if "status" in payload:
        payload["status"] = (payload["status"] or "").upper().replace("-", "_")
        if payload["status"] not in ("TODO", "IN_PROGRESS", "DONE"):
            return api_error("status must be TODO, IN_PROGRESS, or DONE", 400)
    if "assigned_to_user_id" in payload and emp_id is not None:
        return api_error("Only admin can change assignment", 403)
    if not payload:
        return api_error("No valid fields to update", 400)
    row, err = task_service.update_task(task_id, by_employee_id=emp_id, **payload)
    if err:
        return api_error(err, 403 if "Only admin" in err else (404 if "not found" in err else 500))
    return api_success(row, message="Task updated")


@tasks_bp.route("/<int:task_id>/status", methods=["PUT"])
@require_auth_admin_or_employee
def update_task_status(task_id):
    data = request.get_json(silent=True) or {}
    status = (data.get("status") or "").upper().replace("-", "_")
    if status not in ("TODO", "IN_PROGRESS", "DONE"):
        return api_error("status must be TODO, IN_PROGRESS, or DONE", 400)
    row, err = task_service.update_task_status(task_id, status, by_employee_id=_current_employee_id())
    if err:
        return api_error(err, 403 if "Only admin" in err else (404 if "not found" in err else 500))
    return api_success(row, message="Status updated")


@tasks_bp.route("/<int:task_id>", methods=["DELETE"])
@require_admin
def delete_task(task_id):
    ok, err = task_service.delete_task(task_id)
    if err:
        return api_error(err, 404 if "not found" in err else 500)
    return api_success(None, message="Task deleted")
