"""
Chat: send message, store user + AI response, optional task/sprint updates from keywords.
AI stub: ai_generate_response(). Keyword detection: "done", "started", "blocked" to update tasks.
"""
import re
from app.services.db import get_supabase, one, exists
from app.services.project_service import employee_can_access_project
from typing import Tuple, Optional, List


def ai_generate_response(user_message: str, context: dict) -> str:
    """
    Stub for AI Scrum Master response. Replace with real LLM integration later.
    context can include: project_id, user_id, recent tasks, etc.
    """
    # Placeholder: echo + simple suggestion
    msg_lower = (user_message or "").lower()
    if "blocked" in msg_lower:
        return "I've noted you're blocked. Consider updating the task status or adding a comment. Would you like me to mark a task as blocked?"
    if "done" in msg_lower or "completed" in msg_lower:
        return "Great progress! I can mark the related task as DONE if you tell me the task title or ID."
    if "start" in msg_lower or "started" in msg_lower:
        return "I can mark the task as IN_PROGRESS. Which task are you working on?"
    return "Thanks for the update. I'm here to help track progress and update tasks. You can say 'Task X is done' or 'I started Task Y' for automatic updates."


def _extract_task_updates(message: str, sb, user_id: int, project_id: int) -> List[dict]:
    """
    Parse message for keywords and return list of task updates to apply.
    Returns list of { "task_id": int or "title_fragment": str, "status": "DONE"|"IN_PROGRESS" }.
    """
    updates = []
    msg_lower = (message or "").lower()
    # "task X is done" / "task 5 done" / "done task 5"
    if "done" in msg_lower:
        # Try to find task id: "task 5" or "task_id 5"
        m = re.search(r"task\s*[#]?\s*(\d+)", msg_lower, re.I)
        if m:
            updates.append({"task_id": int(m.group(1)), "status": "DONE"})
        else:
            # Try "task <title> is done" - would need to match by title; skip for stub
            pass
    if "started" in msg_lower or "in progress" in msg_lower:
        m = re.search(r"task\s*[#]?\s*(\d+)", msg_lower, re.I)
        if m:
            updates.append({"task_id": int(m.group(1)), "status": "IN_PROGRESS"})
    if "blocked" in msg_lower:
        m = re.search(r"task\s*[#]?\s*(\d+)", msg_lower, re.I)
        if m:
            # Optionally mark or leave as-is; we could add a "BLOCKED" status or just log
            updates.append({"task_id": int(m.group(1)), "status": "IN_PROGRESS"})  # or keep as-is
    return updates


def send_message(project_id: int, user_id: int, message: str, is_admin: bool = False) -> Tuple[Optional[dict], Optional[str]]:
    """
    Store user message, run AI stub, optionally update tasks from keywords, store AI message.
    Returns { "user_message": row, "ai_message": row, "task_updates": [...] }.
    Admin: project must exist. Employee: must be assigned to project.
    """
    sb = get_supabase()
    if is_admin:
        if not exists(sb, "projects", "project_id", project_id):
            return None, "Project not found"
    elif not employee_can_access_project(sb, project_id, user_id):
        return None, "Project not found"
    message = (message or "").strip()
    if not message:
        return None, "message is required"
    try:
        # 1) Store user message
        r1 = sb.table("chat_logs").insert({
            "project_id": project_id,
            "user_id": user_id,
            "sender_type": "USER",
            "message": message,
        }).execute()
        user_row, err = one(r1, "Chat log")
        if err:
            return None, err
        # 2) Apply task updates from keywords
        task_updates = _extract_task_updates(message, sb, user_id, project_id)
        applied = []
        for u in task_updates:
            tid = u.get("task_id")
            if not tid:
                continue
            t = sb.table("tasks").select("task_id, assigned_to_user_id").eq("task_id", tid).limit(1).execute()
            if not (getattr(t, "data", []) or []):
                continue
            task_row = t.data[0]
            if task_row.get("assigned_to_user_id") != user_id:
                continue
            sb.table("tasks").update({"status": u["status"]}).eq("task_id", tid).execute()
            applied.append({"task_id": tid, "status": u["status"]})
        # 3) Generate AI response
        ai_text = ai_generate_response(message, {"project_id": project_id, "user_id": user_id})
        r2 = sb.table("chat_logs").insert({
            "project_id": project_id,
            "user_id": user_id,
            "sender_type": "AI_BOT",
            "message": ai_text,
        }).execute()
        ai_row, err2 = one(r2, "Chat log")
        if err2:
            ai_row = None
        return {
            "user_message": user_row,
            "ai_message": ai_row,
            "task_updates": applied,
        }, None
    except Exception as e:
        return None, str(e)


def list_chat(project_id: int, employee_id: Optional[int], limit: int = 100, is_admin: bool = False) -> Tuple[List[dict], Optional[str]]:
    sb = get_supabase()
    if is_admin:
        if not exists(sb, "projects", "project_id", project_id):
            return [], "Project not found"
    elif employee_id is not None and not employee_can_access_project(sb, project_id, employee_id):
        return [], "Project not found"
    sb = get_supabase()
    try:
        r = sb.table("chat_logs").select("*").eq("project_id", project_id).order("created_at").limit(min(limit, 500)).execute()
        return getattr(r, "data", []) or [], None
    except Exception as e:
        return [], str(e)
