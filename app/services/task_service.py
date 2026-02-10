"""
Task CRUD.
- Admin: all tasks; Employee: only tasks assigned to them (assigned_to_user_id = employee_id).
- Employee can update only their own task status/title/description.
"""
from app.services.db import get_supabase, one, exists
from typing import Tuple, Optional, List, Any


def list_tasks_for_sprint(sprint_id: int, employee_id: Optional[int], sb) -> Tuple[List[dict], Optional[str]]:
    """List tasks in a sprint. If employee_id set, filter to only their tasks."""
    try:
        q = sb.table("tasks").select("*").eq("sprint_id", sprint_id).order("task_id")
        if employee_id is not None:
            q = q.eq("assigned_to_user_id", employee_id)
        r = q.execute()
        return getattr(r, "data", []) or [], None
    except Exception as e:
        return [], str(e)


def list_all_tasks(employee_id: Optional[int]) -> Tuple[List[dict], Optional[str]]:
    """List tasks. Admin: all; Employee: only assigned to them."""
    sb = get_supabase()
    try:
        q = sb.table("tasks").select("*").order("task_id")
        if employee_id is not None:
            q = q.eq("assigned_to_user_id", employee_id)
        r = q.execute()
        return getattr(r, "data", []) or [], None
    except Exception as e:
        return [], str(e)


def get_task(task_id: int, employee_id: Optional[int]) -> Tuple[Optional[dict], Optional[str]]:
    sb = get_supabase()
    r = sb.table("tasks").select("*").eq("task_id", task_id).limit(1).execute()
    row, err = one(r, "Task")
    if err:
        return None, err
    if employee_id is not None and row.get("assigned_to_user_id") != employee_id:
        return None, "Task not found"
    return row, None


def create_task(sprint_id: int, title: str, description: str = "", status: str = "TODO", assigned_to_user_id: Optional[int] = None) -> Tuple[Optional[dict], Optional[str]]:
    if status not in ("TODO", "IN_PROGRESS", "DONE"):
        return None, "status must be TODO, IN_PROGRESS, or DONE"
    sb = get_supabase()
    if not exists(sb, "sprints", "sprint_id", sprint_id):
        return None, "Sprint not found"
    if assigned_to_user_id is not None and not exists(sb, "users", "user_id", assigned_to_user_id):
        return None, "User not found"
    payload = {"sprint_id": sprint_id, "title": title.strip(), "description": (description or "").strip() or None, "status": status}
    if assigned_to_user_id is not None:
        payload["assigned_to_user_id"] = assigned_to_user_id
    try:
        r = sb.table("tasks").insert(payload).execute()
        row, err = one(r, "Task")
        if err:
            return None, err
        return row, None
    except Exception as e:
        return None, str(e)


def update_task(task_id: int, title: Optional[str] = None, description: Optional[str] = None, status: Optional[str] = None, assigned_to_user_id: Optional[int] = None, by_employee_id: Optional[int] = None) -> Tuple[Optional[dict], Optional[str]]:
    """
    Update task. If by_employee_id is set, only that user can update and only if task is assigned to them.
    """
    sb = get_supabase()
    if status is not None and status not in ("TODO", "IN_PROGRESS", "DONE"):
        return None, "status must be TODO, IN_PROGRESS, or DONE"
    current, err = get_task(task_id, by_employee_id)
    if err:
        return None, err
    payload = {}
    if title is not None:
        payload["title"] = title.strip()
    if description is not None:
        payload["description"] = description.strip() or None
    if status is not None:
        payload["status"] = status
    if assigned_to_user_id is not None:
        if by_employee_id is not None:
            return None, "Only admin can change assignment"
        if assigned_to_user_id and not exists(sb, "users", "user_id", assigned_to_user_id):
            return None, "User not found"
        payload["assigned_to_user_id"] = assigned_to_user_id
    if not payload:
        return current, None
    try:
        r = sb.table("tasks").update(payload).eq("task_id", task_id).execute()
        row, err = one(r, "Task")
        if err:
            return None, err
        return row, None
    except Exception as e:
        return None, str(e)


def update_task_status(task_id: int, status: str, by_employee_id: Optional[int] = None) -> Tuple[Optional[dict], Optional[str]]:
    return update_task(task_id, status=status, by_employee_id=by_employee_id)


def delete_task(task_id: int) -> Tuple[bool, Optional[str]]:
    sb = get_supabase()
    try:
        r = sb.table("tasks").delete().eq("task_id", task_id).execute()
        data = getattr(r, "data", []) or []
        if not data:
            return False, "Task not found"
        return True, None
    except Exception as e:
        return False, str(e)
