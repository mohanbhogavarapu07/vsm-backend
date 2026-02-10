"""
Performance logs.
- POST /performance/log: Admin or system.
- GET /performance/me: Employee (own logs only).
- GET /performance/user/{id}, GET /performance/project/{id}: Admin only.
"""
from app.services.db import get_supabase, one, exists
from app.services.project_service import employee_can_access_project
from typing import Tuple, Optional, List, Any


def create_log(user_id: int, task_id: int, accuracy_score: Optional[float] = None, progress_percent: Optional[float] = None, log_date: Any = None) -> Tuple[Optional[dict], Optional[str]]:
    sb = get_supabase()
    if not exists(sb, "users", "user_id", user_id):
        return None, "User not found"
    if not exists(sb, "tasks", "task_id", task_id):
        return None, "Task not found"
    try:
        payload = {"user_id": user_id, "task_id": task_id}
        if accuracy_score is not None:
            payload["accuracy_score"] = accuracy_score
        if progress_percent is not None:
            payload["progress_percent"] = progress_percent
        if log_date is not None:
            payload["log_date"] = log_date
        r = sb.table("performance_logs").insert(payload).execute()
        row, err = one(r, "Performance log")
        if err:
            return None, err
        return row, None
    except Exception as e:
        return None, str(e)


def list_by_user(user_id: int, requesting_employee_id: Optional[int]) -> Tuple[List[dict], Optional[str]]:
    """If requesting_employee_id is set, only allow if requesting_employee_id == user_id (own data)."""
    if requesting_employee_id is not None and requesting_employee_id != user_id:
        return [], "Access denied"
    sb = get_supabase()
    try:
        r = sb.table("performance_logs").select("*").eq("user_id", user_id).order("log_date").execute()
        return getattr(r, "data", []) or [], None
    except Exception as e:
        return [], str(e)


def list_by_project(project_id: int) -> Tuple[List[dict], Optional[str]]:
    """Admin: performance logs for all tasks in sprints of this project."""
    sb = get_supabase()
    try:
        sprints_r = sb.table("sprints").select("sprint_id").eq("project_id", project_id).execute()
        sprint_ids = [s["sprint_id"] for s in (getattr(sprints_r, "data", []) or [])]
        if not sprint_ids:
            return [], None
        tasks_r = sb.table("tasks").select("task_id").in_("sprint_id", sprint_ids).execute()
        task_ids = [t["task_id"] for t in (getattr(tasks_r, "data", []) or [])]
        if not task_ids:
            return [], None
        r = sb.table("performance_logs").select("*").in_("task_id", task_ids).order("log_date").execute()
        return getattr(r, "data", []) or [], None
    except Exception as e:
        return [], str(e)
