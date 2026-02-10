"""Backlog items: CRUD scoped by project. Employee can only access if assigned to project."""
from app.services.db import get_supabase, one
from app.services.project_service import employee_can_access_project
from typing import Tuple, Optional, List

def list_backlog(project_id: int, employee_id: Optional[int]) -> Tuple[List[dict], Optional[str]]:
    sb = get_supabase()
    if employee_id is not None and not employee_can_access_project(sb, project_id, employee_id):
        return [], "Project not found"
    try:
        r = sb.table("backlog_items").select("*").eq("project_id", project_id).order("priority").order("backlog_item_id").execute()
        return getattr(r, "data", []) or [], None
    except Exception as e:
        return [], str(e)


def get_backlog_item(backlog_item_id: int, employee_id: Optional[int]) -> Tuple[Optional[dict], Optional[str]]:
    sb = get_supabase()
    r = sb.table("backlog_items").select("*").eq("backlog_item_id", backlog_item_id).limit(1).execute()
    row, err = one(r, "Backlog item")
    if err:
        return None, err
    if employee_id is not None and not employee_can_access_project(sb, row["project_id"], employee_id):
        return None, "Backlog item not found"
    return row, None


def create_backlog_item(project_id: int, title: str, description: str = "", priority: int = 0) -> Tuple[Optional[dict], Optional[str]]:
    sb = get_supabase()
    try:
        r = sb.table("backlog_items").insert({
            "project_id": project_id,
            "title": title.strip(),
            "description": (description or "").strip() or None,
            "priority": priority,
        }).execute()
        row, err = one(r, "Backlog item")
        if err:
            return None, err
        return row, None
    except Exception as e:
        return None, str(e)


def update_backlog_item(backlog_item_id: int, title: Optional[str] = None, description: Optional[str] = None, priority: Optional[int] = None) -> Tuple[Optional[dict], Optional[str]]:
    sb = get_supabase()
    payload = {}
    if title is not None:
        payload["title"] = title.strip()
    if description is not None:
        payload["description"] = description.strip() or None
    if priority is not None:
        payload["priority"] = priority
    if not payload:
        r = sb.table("backlog_items").select("*").eq("backlog_item_id", backlog_item_id).limit(1).execute()
        return one(r, "Backlog item")
    try:
        r = sb.table("backlog_items").update(payload).eq("backlog_item_id", backlog_item_id).execute()
        row, err = one(r, "Backlog item")
        if err:
            return None, err
        return row, None
    except Exception as e:
        return None, str(e)


def delete_backlog_item(backlog_item_id: int) -> Tuple[bool, Optional[str]]:
    sb = get_supabase()
    try:
        r = sb.table("backlog_items").delete().eq("backlog_item_id", backlog_item_id).execute()
        data = getattr(r, "data", []) or []
        if not data:
            return False, "Backlog item not found"
        return True, None
    except Exception as e:
        return False, str(e)
