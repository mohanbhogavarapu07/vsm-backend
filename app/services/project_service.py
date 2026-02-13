"""
Project and project-assignment services.
- Admin: full CRUD and assignments.
- Employee: only projects they are assigned to (filter in service when employee_id given).
"""
from app.services.db import get_supabase, one, exists
from typing import Tuple, Optional, List, Any


def list_projects(employee_id: Optional[int] = None) -> Tuple[List[dict], Optional[str]]:
    """
    List projects. If employee_id is set (Employee), return only projects they are assigned to.
    If employee_id is None (Admin), return all projects.
    """
    sb = get_supabase()
    try:
        if employee_id is not None:
            # Get project_ids from project_assignments for this employee
            r = sb.table("project_assignments").select("project_id").eq("employee_id", employee_id).execute()
            ids = [row["project_id"] for row in (getattr(r, "data", []) or [])]
            if not ids:
                return [], None
            r = sb.table("projects").select("*").in_("project_id", ids).order("project_id").execute()
        else:
            r = sb.table("projects").select("*").order("project_id").execute()
        data = getattr(r, "data", []) or []
        return data, None
    except Exception as e:
        return [], str(e)


def get_project(project_id: int, employee_id: Optional[int] = None) -> Tuple[Optional[dict], Optional[str]]:
    """
    Get project by id. If employee_id set, verify employee is assigned (else 404).
    """
    sb = get_supabase()
    try:
        r = sb.table("projects").select("*").eq("project_id", project_id).limit(1).execute()
        row, err = one(r, "Project")
        if err:
            return None, err
        if employee_id is not None:
            r2 = sb.table("project_assignments").select("assignment_id").eq("project_id", project_id).eq("employee_id", employee_id).limit(1).execute()
            if not (getattr(r2, "data", []) or []):
                return None, "Project not found"
        return row, None
    except Exception as e:
        return None, str(e)


def create_project(project_name: str, created_by_admin_id: int, description: str = "", start_date: Any = None, end_date: Any = None) -> Tuple[Optional[dict], Optional[str]]:
    sb = get_supabase()
    if not exists(sb, "users", "user_id", created_by_admin_id):
        return None, "User not found"
    try:
        r = sb.table("projects").insert({
            "project_name": project_name.strip(),
            "description": (description or "").strip() or None,
            "created_by_admin_id": created_by_admin_id,
            "start_date": start_date,
            "end_date": end_date,
        }).execute()
        row, err = one(r, "Project")
        if err:
            return None, err
        return row, None
    except Exception as e:
        return None, str(e)


def update_project(project_id: int, project_name: Optional[str] = None, description: Optional[str] = None, start_date: Any = None, end_date: Any = None) -> Tuple[Optional[dict], Optional[str]]:
    sb = get_supabase()
    payload = {}
    if project_name is not None:
        payload["project_name"] = project_name.strip()
    if description is not None:
        payload["description"] = description.strip() or None
    if start_date is not None:
        payload["start_date"] = start_date
    if end_date is not None:
        payload["end_date"] = end_date
    if not payload:
        return get_project(project_id)
    try:
        r = sb.table("projects").update(payload).eq("project_id", project_id).execute()
        row, err = one(r, "Project")
        if err:
            return None, err
        return row, None
    except Exception as e:
        return None, str(e)


def delete_project(project_id: int) -> Tuple[bool, Optional[str]]:
    sb = get_supabase()
    try:
        r = sb.table("projects").delete().eq("project_id", project_id).execute()
        data = getattr(r, "data", []) or []
        if not data:
            return False, "Project not found"
        return True, None
    except Exception as e:
        return False, str(e)


# --- Assignments ---
def list_members(project_id: int) -> Tuple[List[dict], Optional[str]]:
    sb = get_supabase()
    try:
        r = sb.table("project_assignments").select("*").eq("project_id", project_id).order("assignment_id").execute()
        data = getattr(r, "data", []) or []
        # Optionally enrich with user details
        for row in data:
            uid = row.get("employee_id")
            if uid:
                u = sb.table("users").select("full_name, email, role").eq("user_id", uid).limit(1).execute()
                if getattr(u, "data", []) and len(u.data) > 0:
                    row["user"] = u.data[0]
        return data, None
    except Exception as e:
        return [], str(e)


def assign_employee(project_id: int, employee_id: int) -> Tuple[Optional[dict], Optional[str]]:
    sb = get_supabase()
    if not exists(sb, "projects", "project_id", project_id):
        return None, "Project not found"
    if not exists(sb, "users", "user_id", employee_id):
        return None, "User not found"
    
    existing = sb.table("project_assignments").select("project_id").eq("employee_id", employee_id).execute()
    existing_data = getattr(existing, "data", []) or []
    if existing_data:
        existing_project_id = existing_data[0].get("project_id")
        if existing_project_id == project_id:
            return None, "Employee is already assigned to this project"
        # Transfer: remove from old project so they can be assigned here (e.g. all tasks done)
        try:
            sb.table("project_assignments").delete().eq("project_id", existing_project_id).eq("employee_id", employee_id).execute()
        except Exception:
            pass

    try:
        r = sb.table("project_assignments").insert({"project_id": project_id, "employee_id": employee_id}).execute()
        row, err = one(r, "Assignment")
        if err:
            return None, err
        return row, None
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            return None, "Employee is already assigned to this project"
        return None, str(e)


def assign_employees(project_id: int, employee_ids: List[int]) -> Tuple[List[dict], Optional[str]]:
    """Assign multiple employees to a project. Skips already-assigned; returns list of new assignments. Employees can only be assigned to one project."""
    sb = get_supabase()
    if not exists(sb, "projects", "project_id", project_id):
        return [], "Project not found"
    results = []
    errors = []
    for eid in employee_ids:
        if not exists(sb, "users", "user_id", eid):
            errors.append(f"User {eid} not found")
            continue
        
        existing = sb.table("project_assignments").select("project_id").eq("employee_id", eid).execute()
        existing_data = getattr(existing, "data", []) or []
        if existing_data:
            existing_project_id = existing_data[0].get("project_id")
            if existing_project_id == project_id:
                continue  # already in this project, skip
            # Transfer: remove from old project then add to this one
            try:
                sb.table("project_assignments").delete().eq("project_id", existing_project_id).eq("employee_id", eid).execute()
            except Exception:
                pass

        try:
            r = sb.table("project_assignments").insert({"project_id": project_id, "employee_id": eid}).execute()
            row, err = one(r, "Assignment")
            if err:
                errors.append(f"Employee {eid}: {err}")
            else:
                results.append(row)
        except Exception as e:
            if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                errors.append(f"Employee {eid} already assigned to this project")
            else:
                errors.append(f"Employee {eid}: {str(e)}")
    if errors and not results:
        return [], "; ".join(errors)
    return results, None if not errors else "; ".join(errors)


def remove_member(project_id: int, user_id: int) -> Tuple[bool, Optional[str]]:
    sb = get_supabase()
    try:
        r = sb.table("project_assignments").delete().eq("project_id", project_id).eq("employee_id", user_id).execute()
        data = getattr(r, "data", []) or []
        if not data:
            return False, "Assignment not found"
        return True, None
    except Exception as e:
        return False, str(e)


def employee_can_access_project(sb: Any, project_id: int, employee_id: int) -> bool:
    """Return True if employee is assigned to project. Returns False on any Supabase/RLS error."""
    try:
        r = sb.table("project_assignments").select("assignment_id").eq("project_id", project_id).eq("employee_id", employee_id).limit(1).execute()
        return len(getattr(r, "data", []) or []) > 0
    except Exception:
        return False
