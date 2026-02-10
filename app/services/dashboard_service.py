"""
Dashboard aggregates.
- Admin: total projects, employees, sprint status, task counts, bottlenecks, performance averages.
- Employee: my projects, my tasks, my progress, my performance.
"""
from app.services.db import get_supabase
from typing import Tuple, Optional, List, Any


def admin_dashboard() -> Tuple[dict, Optional[str]]:
    sb = get_supabase()
    try:
        projects_r = sb.table("projects").select("project_id", count="exact").execute()
        total_projects = len(getattr(projects_r, "data", []) or [])

        users_r = sb.table("users").select("user_id").eq("role", "EMPLOYEE").execute()
        total_employees = len(getattr(users_r, "data", []) or [])

        sprints_r = sb.table("sprints").select("status").execute()
        sprints = getattr(sprints_r, "data", []) or []
        sprint_status = {"PLANNED": 0, "ACTIVE": 0, "COMPLETED": 0}
        for s in sprints:
            st = (s.get("status") or "PLANNED").upper()
            if st in sprint_status:
                sprint_status[st] += 1

        tasks_r = sb.table("tasks").select("status").execute()
        tasks = getattr(tasks_r, "data", []) or []
        task_status = {"TODO": 0, "IN_PROGRESS": 0, "DONE": 0}
        for t in tasks:
            st = (t.get("status") or "TODO").upper()
            if st in task_status:
                task_status[st] += 1

        # Bottlenecks: tasks IN_PROGRESS (simplified; could add updated_at and threshold)
        bottlenecks = [t for t in tasks if (t.get("status") or "").upper() == "IN_PROGRESS"]

        perf_r = sb.table("performance_logs").select("accuracy_score, progress_percent").execute()
        perf = getattr(perf_r, "data", []) or []
        acc_scores = [p["accuracy_score"] for p in perf if p.get("accuracy_score") is not None]
        prog_scores = [p["progress_percent"] for p in perf if p.get("progress_percent") is not None]
        avg_accuracy = sum(acc_scores) / len(acc_scores) if acc_scores else None
        avg_progress = sum(prog_scores) / len(prog_scores) if prog_scores else None

        return {
            "total_projects": total_projects,
            "total_employees": total_employees,
            "sprint_status_summary": sprint_status,
            "task_status_counts": task_status,
            "bottlenecks_count": len(bottlenecks),
            "bottlenecks_sample": bottlenecks[:10],
            "performance_averages": {"accuracy_score": avg_accuracy, "progress_percent": avg_progress},
        }, None
    except Exception as e:
        return {}, str(e)


def employee_dashboard(employee_id: int) -> Tuple[dict, Optional[str]]:
    sb = get_supabase()
    try:
        assign_r = sb.table("project_assignments").select("project_id").eq("employee_id", employee_id).execute()
        project_ids = [a["project_id"] for a in (getattr(assign_r, "data", []) or [])]
        if not project_ids:
            return {"my_projects": [], "my_tasks": [], "my_performance": [], "summary": {"projects": 0, "tasks": 0}}, None

        projects_r = sb.table("projects").select("*").in_("project_id", project_ids).execute()
        my_projects = getattr(projects_r, "data", []) or []

        tasks_r = sb.table("tasks").select("*").eq("assigned_to_user_id", employee_id).order("task_id").execute()
        my_tasks = getattr(tasks_r, "data", []) or []

        perf_r = sb.table("performance_logs").select("*").eq("user_id", employee_id).order("log_date").execute()
        my_performance = getattr(perf_r, "data", []) or []

        return {
            "my_projects": my_projects,
            "my_tasks": my_tasks,
            "my_performance": my_performance,
            "summary": {"projects": len(my_projects), "tasks": len(my_tasks), "performance_logs": len(my_performance)},
        }, None
    except Exception as e:
        return {}, str(e)
