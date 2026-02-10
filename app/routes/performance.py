"""Performance: POST /performance/log (Admin), GET /performance/me (Employee), GET /performance/user/{id} and /project/{id} (Admin)."""
from flask import Blueprint, request, g
from app.middleware.auth import require_admin, require_auth_admin_or_employee
from app.services import performance_service
from app.utils.response import api_success, api_error
from app.utils.validators import required_keys, int_or_none

bp = Blueprint("performance", __name__, url_prefix="/performance")


@bp.route("/log", methods=["POST"])
@bp.route("/logs", methods=["POST"])
@require_admin
def create_log():
    data = request.get_json(silent=True) or {}
    err = required_keys(data, ["user_id", "task_id"])
    if err:
        return api_error(err, 400)
    user_id = int_or_none(data.get("user_id"))
    task_id = int_or_none(data.get("task_id"))
    if user_id is None or task_id is None:
        return api_error("user_id and task_id must be valid integers", 400)
    row, err = performance_service.create_log(
        user_id,
        task_id,
        accuracy_score=data.get("accuracy_score"),
        progress_percent=data.get("progress_percent"),
        log_date=data.get("log_date"),
    )
    if err:
        return api_error(err, 400 if "not found" in err else 500)
    return api_success(row, message="Performance log created", status=201)


@bp.route("/me", methods=["GET"])
@require_auth_admin_or_employee
def my_performance():
    """Employee: own performance only. Admin can also call this for self."""
    user_id = g.current_user["user_id"]
    # Pass requesting_employee_id so Employee can only see own; Admin passes None in list_by_user
    is_employee = g.current_user.get("role") == "EMPLOYEE"
    data, err = performance_service.list_by_user(user_id, requesting_employee_id=user_id if is_employee else None)
    if err:
        return api_error(err, 403 if "Access denied" in err else 500)
    return api_success({"performance_logs": data, "count": len(data)})


@bp.route("/user/<int:user_id>", methods=["GET"])
@require_admin
def get_by_user(user_id):
    data, err = performance_service.list_by_user(user_id, requesting_employee_id=None)
    if err:
        return api_error(err, 500)
    return api_success({"performance_logs": data, "count": len(data)})


@bp.route("/project/<int:project_id>", methods=["GET"])
@require_admin
def get_by_project(project_id):
    data, err = performance_service.list_by_project(project_id)
    if err:
        return api_error(err, 500)
    return api_success({"performance_logs": data, "count": len(data)})
