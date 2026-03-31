"""
Chat: send message, store user + AI response, optional task/sprint updates from keywords.
AI stub: ai_generate_response(). Keyword detection: "done", "started", "blocked" to update tasks.
"""
import re
import os
from app.services.db import get_supabase, one, exists
from app.services.project_service import employee_can_access_project
from typing import Tuple, Optional, List
from app.services.rag_service import retrieve_context
from groq import Groq


import json

def tool_get_user_performance(user_name: str, project_id: int) -> str:
    """Fetch live performance metrics for a specific user by name."""
    sb = get_supabase()
    try:
        users_r = sb.table("users").select("user_id, full_name, role").ilike("full_name", f"%{user_name}%").execute()
        users = getattr(users_r, "data", []) or []
        if not users:
            return json.dumps({"error": f"No user found matching '{user_name}' in the database. Please ensure the spelling is correct."})
            
        u = users[0]
        u_id = u["user_id"]
        
        perf_r = sb.table("performance_logs").select("*").eq("user_id", u_id).execute()
        perf_logs = getattr(perf_r, "data", []) or []
        
        acc_scores = [pl["accuracy_score"] for pl in perf_logs if pl.get("accuracy_score") is not None]
        prog_scores = [pl["progress_percent"] for pl in perf_logs if pl.get("progress_percent") is not None]
        
        assign_r = sb.table("project_assignments").select("assignment_id").eq("project_id", project_id).eq("employee_id", u_id).execute()
        assigned = len(getattr(assign_r, "data", []) or []) > 0
        
        return json.dumps({
            "user": u["full_name"],
            "role": u["role"],
            "assigned_to_this_context_project": assigned,
            "average_accuracy_score": round(sum(acc_scores)/len(acc_scores), 1) if acc_scores else "No logs found",
            "average_progress_percent": round(sum(prog_scores)/len(prog_scores), 1) if prog_scores else "No logs found",
            "total_performance_logs_recorded": len(perf_logs)
        })
    except Exception as e:
        return json.dumps({"error": str(e)})

def tool_get_project_status(project_id: int) -> str:
    """Fetch live project status including sprints and tasks."""
    sb = get_supabase()
    try:
        proj_r = sb.table("projects").select("project_name, description").eq("project_id", project_id).limit(1).execute()
        p = getattr(proj_r, "data", [{}])[0] if getattr(proj_r, "data", []) else {}
        
        sprints_r = sb.table("sprints").select("*").eq("project_id", project_id).execute()
        sprints = getattr(sprints_r, "data", []) or []
        
        if sprints:
            sprint_ids = [s["sprint_id"] for s in sprints]
            tasks_r = sb.table("tasks").select("task_id, sprint_id, title, status, assigned_to_user_id").in_("sprint_id", sprint_ids).execute()
            tasks = getattr(tasks_r, "data", []) or []
            
            assigned_user_ids = list(set([t["assigned_to_user_id"] for t in tasks if t.get("assigned_to_user_id")]))
            user_map = {}
            if assigned_user_ids:
                users_r = sb.table("users").select("user_id, full_name").in_("user_id", assigned_user_ids).execute()
                for u in getattr(users_r, "data", []) or []:
                    user_map[u["user_id"]] = u["full_name"]
            
            res_sprints = []
            for s in sprints:
                stasks = []
                for t in tasks:
                    if t.get("sprint_id") == s["sprint_id"]:
                        full_name = user_map.get(t.get("assigned_to_user_id"), "Unassigned")
                        stasks.append({
                            "task_id": t.get("task_id"),
                            "title": t.get("title"),
                            "status": t.get("status"),
                            "assigned_to": full_name
                        })
                res_sprints.append({
                    "sprint_name": s["sprint_name"],
                    "status": s["status"],
                    "tasks": stasks
                })
            return json.dumps({
                "project_name": p.get("project_name"),
                "sprints": res_sprints
            })
        return json.dumps({"status": f"Project {p.get('project_name')} has absolutely no sprints or tasks created yet."})
    except Exception as e:
        return json.dumps({"error": str(e)})


def tool_search_global_database(query: str, user_id: int) -> str:
    """Search for Sprints or Projects by name globally across all authorized user projects."""
    sb = get_supabase()
    try:
        assign_r = sb.table("project_assignments").select("project_id").eq("employee_id", user_id).execute()
        valid_project_ids = [a["project_id"] for a in getattr(assign_r, "data", []) or []]
        
        user_r = sb.table("users").select("role").eq("user_id", user_id).limit(1).execute()
        role = getattr(user_r, "data", [{}])[0].get("role")
        if role == "ADMIN":
            proj_r = sb.table("projects").select("project_id").execute()
            valid_project_ids = [p["project_id"] for p in getattr(proj_r, "data", []) or []]
            
        if not valid_project_ids:
            return json.dumps({"error": "You do not have access to any projects in the database."})
            
        results = []
        proj_r = sb.table("projects").select("project_id, project_name, description").in_("project_id", valid_project_ids).ilike("project_name", f"%{query}%").execute()
        p_matches = getattr(proj_r, "data", []) or []
        for p in p_matches:
            results.append({"type": "project", "id": p["project_id"], "name": p["project_name"], "description": p["description"]})
            
        sprints_r = sb.table("sprints").select("sprint_id, sprint_name, status, project_id").in_("project_id", valid_project_ids).ilike("sprint_name", f"%{query}%").execute()
        s_matches = getattr(sprints_r, "data", []) or []
        
        if s_matches:
            sprint_pids = list(set([s["project_id"] for s in s_matches]))
            sp_r = sb.table("projects").select("project_id, project_name").in_("project_id", sprint_pids).execute()
            sp_map = {p["project_id"]: p["project_name"] for p in (getattr(sp_r, "data", []) or [])}
            for s in s_matches:
                results.append({
                    "type": "sprint", 
                    "sprint_name": s["sprint_name"], 
                    "status": s["status"], 
                    "belongs_to_project": sp_map.get(s["project_id"], str(s["project_id"])),
                    "project_id": s["project_id"]
                })
        
        if not results:
            return json.dumps({"status": f"No projects or sprints found matching your query '{query}' across all your authorized domains."})
        return json.dumps({"search_matches": results})
    except Exception as e:
        return json.dumps({"error": str(e)})


def classify_query(query: str) -> str:
    q = query.lower()
    if any(k in q for k in ["task", "tasks", "sprint", "project", "status", "user", "performance", "progress", "done", "started", "blocked", "daily"]):
        return "STRUCTURED"
    elif any(k in q for k in ["explain", "why", "how", "document", "guide", "concept", "meaning"]):
        return "UNSTRUCTURED"
    return "GENERAL"


def format_response_with_llm(data: str, user_message: str, history=None) -> str:
    groq_api_key = os.environ.get("GROQ_API_KEY")
    if not groq_api_key:
        return "Groq API key not configured. Please set GROQ_API_KEY."
    
    try:
        client = Groq(api_key=groq_api_key)
        prompt = f"""You are a professional, expert Enterprise Scrum Master.
Your job is to read the backend system's Data output and deliver a highly polished, natural, conversational response to the user.

Rules for Text Formatting:
1. NEVER output raw JSON, dictionaries, array brackets, or code blocks containing data.
2. DO NOT use ANY Markdown formatting (NO asterisks `**`, no hash headers `#`). The frontend UI only supports plain text strings. Use regular spaces, newlines, and dashes `-` for bullet points.
3. Keep the tone empathetic and encouraging, like a real Agile Coach. Do not sound like a robot reading a spreadsheet.
4. Do not simply regurgitate data. Summarize what it means (e.g., if there are no tasks, explain that the sprint is empty and suggest next steps).
5. If the Data says a project/sprint/user is not found, confidently state that you don't have access or it doesn't exist, rather than saying "the provided data doesn't mention it".
6. If the Data says a task was successfully updated, enthusiastically confirm the update to the user.

The user's original query was: "{user_message}"

Backend System Data:
{data}
"""
        messages = [{"role": "system", "content": prompt}]
        if history:
            for row in history:
                role = "user" if row.get("sender_type") == "USER" else "assistant"
                if row.get("message"):
                    messages.append({"role": role, "content": row.get("message")})
        messages.append({"role": "user", "content": user_message})

        chat_completion = client.chat.completions.create(
            messages=messages,
            model="llama-3.1-8b-instant",
            temperature=0.0
        )
        content = chat_completion.choices[0].message.content
        if content:
            # Forcibly strip stubborn markdown formatting since frontend lacks a parser
            content = content.replace("**", "").replace("###", "").replace("##", "").replace("#", "")
        return content
    except Exception as e:
        print(f"Error calling format LLM: {e}")
        return "There was an error formatting the AI response."


def fuzzy_match(query: str, db_strings: list) -> str:
    stop_words = {"can", "i", "know", "the", "status", "of", "project", "sprint", "task", "about", "show", "me", "tell", "what", "is", "a", "an", "for", "on", "in", "it"}
    query_words = set(re.findall(r'\w+', query.lower())) - stop_words
    
    best_match = ""
    max_overlap = 0
    for db_str in db_strings:
        db_words = set(re.findall(r'\w+', db_str.lower())) - stop_words
        if not db_words: continue
        overlap = len(query_words.intersection(db_words))
        
        if db_str.lower() in query.lower():
            return db_str
            
        if overlap > max_overlap and overlap >= max(1, len(db_words) // 2):
            max_overlap = overlap
            best_match = db_str
            
    return best_match


def extract_entities_with_llm(user_message: str, history: list) -> dict:
    groq_api_key = os.environ.get("GROQ_API_KEY")
    if not groq_api_key:
        return {"target_project": None, "target_sprint": None, "target_user": None}
    
    try:
        client = Groq(api_key=groq_api_key)
        history_str = ""
        for h in history[-2:]:
            if h.get("message"):
                role = h.get("sender_type", "USER")
                history_str += f"{role}: {h['message']}\n"
                
        prompt = f"""You are a precise JSON entity extractor.
Extract the exact target project, sprint, and user names from the Current Query.
Use the Recent Conversation history ONLY to resolve pronouns (e.g., 'it', 'he', 'that sprint').
If the Current Query introduces a NEW topic (e.g., asks about 'Project B' or 'User C' overriding the past context), DO NOT extract entities from the past conversation.

Recent Conversation:
{history_str}

Current Query: "{user_message}"

Return EXACTLY a pure JSON object with keys:
"target_project" (string or null),
"target_sprint" (string or null),
"target_user" (string or null)
"""
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        content = chat_completion.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        print(f"Error extracting entities: {e}")
        return {"target_project": None, "target_sprint": None, "target_user": None}


def ai_generate_response(user_message: str, context: dict) -> str:
    """
    Deterministic Router Architecture (Replaces autonomous Agents)
    """
    project_id = context.get("project_id")
    user_id = context.get("user_id")
    history = context.get("history", [])
    
    query_type = classify_query(user_message)
    
    if query_type == "STRUCTURED":
        q = user_message.lower()
        sb = get_supabase()
        
        entities = extract_entities_with_llm(user_message, history)
        target_project_str = entities.get("target_project")
        target_sprint_str = entities.get("target_sprint")
        target_user_str = entities.get("target_user")
        
        # Find all authorized projects globally
        assign_r = sb.table("project_assignments").select("project_id").eq("employee_id", user_id).execute()
        valid_project_ids = [a["project_id"] for a in getattr(assign_r, "data", []) or []]
        admin_r = sb.table("users").select("role").eq("user_id", user_id).limit(1).execute()
        if getattr(admin_r, "data", [{}])[0].get("role") == "ADMIN":
            proj_all_r = sb.table("projects").select("project_id").execute()
            valid_project_ids = [p["project_id"] for p in getattr(proj_all_r, "data", []) or []]
            
        effective_project_id = project_id
        
        # 1. Match specific Project
        if valid_project_ids and target_project_str:
            proj_r = sb.table("projects").select("project_id, project_name").in_("project_id", valid_project_ids).execute()
            all_projs = getattr(proj_r, "data", []) or []
            if all_projs:
                matched_proj = fuzzy_match(target_project_str, [p["project_name"] for p in all_projs])
                if matched_proj:
                    effective_project_id = next((p["project_id"] for p in all_projs if p["project_name"] == matched_proj), effective_project_id)
        
        # 2. Match specific Sprint
        matched_sprint = ""
        if valid_project_ids and target_sprint_str:
            sprints_r = sb.table("sprints").select("sprint_id, sprint_name, project_id").in_("project_id", valid_project_ids).execute()
            all_sprints = getattr(sprints_r, "data", []) or []
            if all_sprints:
                matched_sprint = fuzzy_match(target_sprint_str, [s["sprint_name"] for s in all_sprints])
                if matched_sprint:
                    effective_project_id = next((s["project_id"] for s in all_sprints if s["sprint_name"] == matched_sprint), effective_project_id)
                    
        # 3. Match specific User
        matched_user = ""
        if target_user_str:
            users_r = sb.table("users").select("full_name").execute()
            all_users = getattr(users_r, "data", []) or []
            if all_users:
                user_matches = set()
                for u in all_users:
                    user_matches.add(u["full_name"])
                    user_matches.add(u["full_name"].split()[0])
                m_user = fuzzy_match(target_user_str, list(user_matches))
                if m_user:
                    for u in all_users:
                        if m_user in u["full_name"]:
                            matched_user = u["full_name"]
                            break
                            
        # Final Payload Routing Execution
        if matched_user:
            data = tool_get_user_performance(matched_user, effective_project_id)
        elif matched_sprint:
            raw_data = tool_get_project_status(effective_project_id)
            data = f"CRITICAL PRIORITY: Extract and focus strictly on returning detailed sprint progress, task distributions, and current active status ONLY for Sprint Name: '{matched_sprint}'. Do NOT just state what project it belongs to.\n\n" + raw_data
        else:
            data = tool_get_project_status(effective_project_id)
            
        applied = context.get("task_updates_applied", [])
        if applied:
            data += "\n\nBACKEND ACTION: The system successfully updated the following task IDs to their new statuses: " + str(applied)
            
        return format_response_with_llm(data, user_message, history)

    elif query_type == "UNSTRUCTURED":
        rag_context = ""
        if project_id:
            rag_context = retrieve_context(project_id, user_message, top_k=5, use_top_k=3)
        if not rag_context or len(rag_context.strip()) == 0:
            data = json.dumps({"status": "No knowledge base documents found regarding this technical query. The database is empty of unstructured text."})
        else:
            data = "Document Search Context:\n" + rag_context
        return format_response_with_llm(data, user_message, history)

    else:
        # GENERAL
        data = json.dumps({"general_query": user_message, "instruction": "Provide expert general agile or scrum knowledge. Answer naturally. Do not invent actual project or personnel data."})
        return format_response_with_llm(data, user_message, history)


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
    
    # Fallback if project_id invalid/hardcoded from frontend
    if is_admin:
        if not exists(sb, "projects", "project_id", project_id):
            r = sb.table("projects").select("project_id").limit(1).execute()
            if getattr(r, "data", []) and len(r.data) > 0:
                project_id = r.data[0]["project_id"]
            else:
                return None, "Project not found"
    else:
        if not employee_can_access_project(sb, project_id, user_id):
            r = sb.table("project_assignments").select("project_id").eq("employee_id", user_id).limit(1).execute()
            if getattr(r, "data", []) and len(r.data) > 0:
                project_id = r.data[0]["project_id"]
            else:
                return None, "Project not found"
                
    message = (message or "").strip()
    if not message:
        return None, "message is required"
    try:
        hist_r = sb.table("chat_logs").select("sender_type, message").eq("project_id", project_id).eq("user_id", user_id).order("created_at", desc=True).limit(6).execute()
        history = getattr(hist_r, "data", []) or []
        history.reverse()
        
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
        ai_text = ai_generate_response(message, {
            "project_id": project_id, 
            "user_id": user_id, 
            "history": history,
            "task_updates_applied": applied
        })
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
