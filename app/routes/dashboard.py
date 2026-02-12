"""Dashboards: GET /dashboard (role-based), GET /dashboard/admin (Admin), GET /dashboard/employee (Employee)."""
from flask import Blueprint, g
from app.middleware.auth import require_admin, require_auth_admin_or_employee
from app.services import dashboard_service
from app.utils.response import api_success, api_error

bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


@bp.route("", methods=["GET"])
@require_auth_admin_or_employee
def dashboard():
    """Single endpoint: returns admin or employee dashboard based on current user role. Avoids 403 when frontend calls one URL."""
    role = g.current_user.get("role")
    user_id = g.current_user.get("user_id")
    if role == "ADMIN":
        data, err = dashboard_service.admin_dashboard()
    else:
        data, err = dashboard_service.employee_dashboard(user_id)
    if err:
        return api_error(err, 500)
    return api_success(data)


@bp.route("/admin", methods=["GET"])
@require_admin
def admin_dashboard():
    data, err = dashboard_service.admin_dashboard()
    if err:
        return api_error(err, 500)
    return api_success(data)


@bp.route("/employee", methods=["GET"])
@require_auth_admin_or_employee
def employee_dashboard():
    data, err = dashboard_service.employee_dashboard(g.current_user["user_id"])
    if err:
        return api_error(err, 500)
    return api_success(data)
