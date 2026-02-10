"""Sprint CRUD. Employee can only access sprints for projects they are assigned to."""
from app.services.db import get_supabase, one, exists
from app.services.project_service import employee_can_access_project
from typing import Tuple, Optional, List, Any


def list_sprints(project_id: int, employee_id: Optional[int]) -> Tuple[List[dict], Optional[str]]:
    sb = get_supabase()
    if employee_id is not None and not employee_can_access_project(sb, project_id, employee_id):
        return [], "Project not found"
    try:
        r = sb.table("sprints").select("*").eq("project_id", project_id).order("sprint_id").execute()
        return getattr(r, "data", []) or [], None
    except Exception as e:
        return [], str(e)


def get_sprint(sprint_id: int, employee_id: Optional[int]) -> Tuple[Optional[dict], Optional[str]]:
    sb = get_supabase()
    r = sb.table("sprints").select("*").eq("sprint_id", sprint_id).limit(1).execute()
    row, err = one(r, "Sprint")
    if err:
        return None, err
    if employee_id is not None and not employee_can_access_project(sb, row["project_id"], employee_id):
        return None, "Sprint not found"
    return row, None


def create_sprint(project_id: int, sprint_name: str, start_date: Any = None, end_date: Any = None, status: str = "PLANNED") -> Tuple[Optional[dict], Optional[str]]:
    if status not in ("PLANNED", "ACTIVE", "COMPLETED"):
        return None, "status must be PLANNED, ACTIVE, or COMPLETED"
    sb = get_supabase()
    if not exists(sb, "projects", "project_id", project_id):
        return None, "Project not found"
    try:
        r = sb.table("sprints").insert({
            "project_id": project_id,
            "sprint_name": sprint_name.strip(),
            "start_date": start_date,
            "end_date": end_date,
            "status": status,
        }).execute()
        row, err = one(r, "Sprint")
        if err:
            return None, err
        return row, None
    except Exception as e:
        return None, str(e)


def update_sprint(sprint_id: int, sprint_name: Optional[str] = None, start_date: Any = None, end_date: Any = None, status: Optional[str] = None) -> Tuple[Optional[dict], Optional[str]]:
    if status is not None and status not in ("PLANNED", "ACTIVE", "COMPLETED"):
        return None, "status must be PLANNED, ACTIVE, or COMPLETED"
    sb = get_supabase()
    payload = {}
    if sprint_name is not None:
        payload["sprint_name"] = sprint_name.strip()
    if start_date is not None:
        payload["start_date"] = start_date
    if end_date is not None:
        payload["end_date"] = end_date
    if status is not None:
        payload["status"] = status
    if not payload:
        return get_sprint(sprint_id, None)
    try:
        r = sb.table("sprints").update(payload).eq("sprint_id", sprint_id).execute()
        row, err = one(r, "Sprint")
        if err:
            return None, err
        return row, None
    except Exception as e:
        return None, str(e)


def delete_sprint(sprint_id: int) -> Tuple[bool, Optional[str]]:
    sb = get_supabase()
    try:
        r = sb.table("sprints").delete().eq("sprint_id", sprint_id).execute()
        data = getattr(r, "data", []) or []
        if not data:
            return False, "Sprint not found"
        return True, None
    except Exception as e:
        return False, str(e)
