import os
import urllib.error
import urllib.request

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from supabase import create_client

app = Flask(__name__)

# Load environment from .env (local dev only)
load_dotenv()

# CORS allowlist (comma-separated). Example: "http://localhost:3000,https://yourapp.com"
_cors_origins_raw = os.environ.get("CORS_ORIGINS", "").strip()
cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]

# If you don't set CORS_ORIGINS, default to localhost dev frontends.
if not cors_origins:
    cors_origins = ["http://localhost:3000", "http://localhost:5173"]

CORS(
    app,
    resources={r"/api/*": {"origins": cors_origins}},
    supports_credentials=True,
)

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['DEBUG'] = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'

# Supabase configuration
app.config["SUPABASE_URL"] = os.environ.get("SUPABASE_URL", "").strip()

def _looks_like_jwt(key: str) -> bool:
    # Supabase anon/service_role keys are JWTs (three base64url parts separated by dots)
    return bool(key) and key.startswith("eyJ") and key.count(".") >= 2


# Use service_role key ONLY on backend. If someone accidentally pastes a non-JWT key
# (e.g., a publishable key), ignore it and fall back to the anon JWT.
_service_role = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
_anon = os.environ.get("SUPABASE_ANON_KEY", "").strip()

if _looks_like_jwt(_service_role):
    app.config["SUPABASE_KEY"] = _service_role
    app.config["SUPABASE_KEY_KIND"] = "service_role"
elif _looks_like_jwt(_anon):
    app.config["SUPABASE_KEY"] = _anon
    app.config["SUPABASE_KEY_KIND"] = "anon"
else:
    app.config["SUPABASE_KEY"] = (_service_role or _anon).strip()
    app.config["SUPABASE_KEY_KIND"] = "unknown"

app.config["SUPABASE_PING_TABLE"] = os.environ.get("SUPABASE_PING_TABLE", "").strip()

supabase = None
if app.config["SUPABASE_URL"] and app.config["SUPABASE_KEY"]:
    supabase = create_client(app.config["SUPABASE_URL"], app.config["SUPABASE_KEY"])


def _check_supabase_db_connection():
    """
    Performs a service-level connectivity check to Supabase without relying on any table.
    Returns (ok: bool, message: str).
    """
    if not supabase:
        if not app.config.get("SUPABASE_URL"):
            return False, "Supabase is not configured (missing SUPABASE_URL)."
        return (
            False,
            "Supabase is not configured (missing/invalid key). Use the JWT-shaped keys from Supabase Dashboard → Settings → API (anon key or service_role key).",
        )

    try:
        base_url = app.config["SUPABASE_URL"].rstrip("/")
        key = app.config["SUPABASE_KEY"]

        def _get(url: str, accept: str | None = None) -> int:
            headers = {"apikey": key, "Authorization": f"Bearer {key}"}
            if accept:
                headers["Accept"] = accept
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.getcode()

        # 1) Auth service health (does not depend on DB schema/tables)
        auth_status = _get(f"{base_url}/auth/v1/health")

        # 2) PostgREST OpenAPI (checks REST layer reachability; still no table required)
        # Some deployments return 200 with OpenAPI JSON when Accept is set.
        rest_status = _get(f"{base_url}/rest/v1/", accept="application/openapi+json")

        if 200 <= auth_status < 300 and 200 <= rest_status < 300:
            kind = app.config.get("SUPABASE_KEY_KIND", "unknown")
            return True, f"Supabase connected successfully (auth + rest services reachable, key={kind})."
        return False, f"Supabase connectivity check failed (auth={auth_status}, rest={rest_status})."
    except urllib.error.HTTPError as e:
        return False, f"Supabase connectivity check failed (HTTP {e.code}): {e.reason}"
    except urllib.error.URLError as e:
        return False, f"Supabase connectivity check failed (network): {e.reason}"
    except Exception as e:
        return False, f"Supabase connectivity check failed: {e}"


# --- Helpers for Supabase-backed routes ---
def _db():
    """Require Supabase; return (None, None) if ok, else (response, status_code)."""
    if not supabase:
        return jsonify({"error": "Database not configured"}), 503
    return None, None


def _get_json(required_keys=None):
    """
    Parse JSON body. Returns (data_dict, None) or (None, (response, status)).
    If required_keys is set, validates presence and returns 400 when missing.
    """
    data = request.get_json(silent=True)
    if data is None:
        return None, (jsonify({"error": "Invalid or missing JSON body"}), 400)
    if required_keys:
        missing = [k for k in required_keys if not data.get(k) and data.get(k) != 0]
        if missing:
            return None, (jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400)
    return data, None


def _one(resp, name="Resource"):
    """Get single row from Supabase response; return (data, None) or (None, (jsonify_err, status))."""
    data = getattr(resp, "data", None) or []
    if not data or len(data) == 0:
        return None, (jsonify({"error": f"{name} not found"}), 404)
    return data[0], None


def _exists(table, column, value):
    """Return True if a row exists with column=value, else False."""
    try:
        resp = supabase.table(table).select(column).eq(column, value).limit(1).execute()
        data = getattr(resp, "data", None) or []
        return len(data) > 0
    except Exception:
        return False


def _require_exists(table, column, value, name="Resource"):
    """Return None if exists; else (jsonify_err, 404)."""
    if _exists(table, column, value):
        return None
    return (jsonify({"error": f"{name} not found"}), 404)


def _int_or_none(v):
    """Parse int; return None for None or invalid."""
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


# --- Home & docs ---
@app.route('/', methods=['GET'])
def home():
    """Home endpoint with full API index"""
    return jsonify({
        "message": "Welcome to Scrum Master API",
        "version": "1.0.0",
        "endpoints": {
            "users": "GET/POST /api/users, GET/PUT/DELETE /api/users/<id>",
            "projects": "GET/POST /api/projects, GET/PUT/DELETE /api/projects/<id>",
            "assignments": "GET/POST /api/projects/<id>/assignments, DELETE /api/projects/<id>/assignments/<assignment_id>",
            "backlog": "GET/POST /api/projects/<id>/backlog, GET/PUT/DELETE /api/backlog/<id>",
            "sprints": "GET/POST /api/projects/<id>/sprints, GET/PUT/DELETE /api/sprints/<id>",
            "tasks": "GET/POST /api/sprints/<id>/tasks, GET/PUT/DELETE /api/tasks/<id>, GET /api/users/<id>/tasks",
            "chat": "GET/POST /api/projects/<id>/chat",
            "performance_logs": "GET/POST /api/performance_logs, GET/PUT/DELETE /api/performance_logs/<id>, GET /api/users/<id>/performance",
        }
    })


# ========== USERS ==========
@app.route('/api/users', methods=['GET'])
def list_users():
    err, status = _db()
    if err is not None:
        return err, status
    role = request.args.get('role')
    try:
        q = supabase.table("users").select("*").order("user_id")
        if role and role in ("ADMIN", "EMPLOYEE"):
            q = q.eq("role", role)
        resp = q.execute()
        data = getattr(resp, "data", []) or []
        return jsonify({"users": data, "count": len(data)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/users', methods=['POST'])
def create_user():
    err, status = _db()
    if err is not None:
        return err, status
    data, err = _get_json(required_keys=["full_name", "email", "password_hash", "role"])
    if err is not None:
        return err
    role = (data.get("role") or "").upper()
    if role not in ("ADMIN", "EMPLOYEE"):
        return jsonify({"error": "role must be ADMIN or EMPLOYEE"}), 400
    if not str(data.get("email", "")).strip():
        return jsonify({"error": "email cannot be empty"}), 400
    try:
        payload = {
            "full_name": str(data["full_name"]).strip(),
            "email": str(data["email"]).strip(),
            "password_hash": data["password_hash"],
            "role": role,
        }
        resp = supabase.table("users").insert(payload).execute()
        row, err = _one(resp, "User")
        if err:
            return err
        return jsonify(row), 201
    except Exception as e:
        msg = str(e).lower()
        if "unique" in msg or "duplicate" in msg or "email" in msg:
            return jsonify({"error": "A user with this email already exists"}), 409
        return jsonify({"error": str(e)}), 500


@app.route('/api/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    err, status = _db()
    if err is not None:
        return err, status
    try:
        resp = supabase.table("users").select("*").eq("user_id", user_id).limit(1).execute()
        row, err = _one(resp, "User")
        if err:
            return err
        return jsonify(row)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    err, status = _db()
    if err is not None:
        return err, status
    data = request.get_json(silent=True) or {}
    allowed = {"full_name", "email", "password_hash", "role"}
    payload = {k: v for k, v in data.items() if k in allowed and v is not None}
    if "role" in payload and payload["role"] not in ("ADMIN", "EMPLOYEE"):
        return jsonify({"error": "role must be ADMIN or EMPLOYEE"}), 400
    if not payload:
        return jsonify({"error": "No valid fields to update"}), 400
    try:
        resp = supabase.table("users").update(payload).eq("user_id", user_id).execute()
        row, err = _one(resp, "User")
        if err:
            return err
        return jsonify(row)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    err, status = _db()
    if err is not None:
        return err, status
    try:
        resp = supabase.table("users").delete().eq("user_id", user_id).execute()
        data = getattr(resp, "data", None) or []
        if not data:
            return jsonify({"error": "User not found"}), 404
        return jsonify({"message": "User deleted"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ========== PROJECTS ==========
@app.route('/api/projects', methods=['GET'])
def list_projects():
    err, status = _db()
    if err is not None:
        return err, status
    try:
        resp = supabase.table("projects").select("*").order("project_id").execute()
        data = getattr(resp, "data", []) or []
        return jsonify({"projects": data, "count": len(data)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/projects', methods=['POST'])
def create_project():
    err, status = _db()
    if err is not None:
        return err, status
    data, err = _get_json(required_keys=["project_name", "created_by_admin_id"])
    if err is not None:
        return err
    admin_id = _int_or_none(data.get("created_by_admin_id"))
    if admin_id is None:
        return jsonify({"error": "created_by_admin_id must be a valid integer"}), 400
    err_resp = _require_exists("users", "user_id", admin_id, "User (admin)")
    if err_resp is not None:
        return err_resp
    try:
        payload = {
            "project_name": str(data["project_name"]).strip(),
            "description": (data.get("description") or "").strip() or None,
            "created_by_admin_id": admin_id,
            "start_date": data.get("start_date"),
            "end_date": data.get("end_date"),
        }
        resp = supabase.table("projects").insert(payload).execute()
        row, err = _one(resp, "Project")
        if err:
            return err
        return jsonify(row), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/projects/<int:project_id>', methods=['GET'])
def get_project(project_id):
    err, status = _db()
    if err is not None:
        return err, status
    try:
        resp = supabase.table("projects").select("*").eq("project_id", project_id).limit(1).execute()
        row, err = _one(resp, "Project")
        if err:
            return err
        return jsonify(row)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/projects/<int:project_id>', methods=['PUT'])
def update_project(project_id):
    err, status = _db()
    if err is not None:
        return err, status
    data = request.get_json(silent=True) or {}
    allowed = {"project_name", "description", "start_date", "end_date"}
    payload = {k: v for k, v in data.items() if k in allowed}
    if not payload:
        return jsonify({"error": "No valid fields to update"}), 400
    try:
        resp = supabase.table("projects").update(payload).eq("project_id", project_id).execute()
        row, err = _one(resp, "Project")
        if err:
            return err
        return jsonify(row)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/projects/<int:project_id>', methods=['DELETE'])
def delete_project(project_id):
    err, status = _db()
    if err is not None:
        return err, status
    try:
        resp = supabase.table("projects").delete().eq("project_id", project_id).execute()
        data = getattr(resp, "data", None) or []
        if not data:
            return jsonify({"error": "Project not found"}), 404
        return jsonify({"message": "Project deleted"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ========== PROJECT ASSIGNMENTS ==========
@app.route('/api/projects/<int:project_id>/assignments', methods=['GET'])
def list_assignments(project_id):
    err, status = _db()
    if err is not None:
        return err, status
    err_resp = _require_exists("projects", "project_id", project_id, "Project")
    if err_resp is not None:
        return err_resp
    try:
        resp = supabase.table("project_assignments").select("*").eq("project_id", project_id).order("assignment_id").execute()
        data = getattr(resp, "data", []) or []
        return jsonify({"assignments": data, "count": len(data)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/projects/<int:project_id>/assignments', methods=['POST'])
def create_assignment(project_id):
    err, status = _db()
    if err is not None:
        return err, status
    err_resp = _require_exists("projects", "project_id", project_id, "Project")
    if err_resp is not None:
        return err_resp
    data, err = _get_json(required_keys=["employee_id"])
    if err is not None:
        return err
    employee_id = _int_or_none(data.get("employee_id"))
    if employee_id is None:
        return jsonify({"error": "employee_id must be a valid integer"}), 400
    err_resp = _require_exists("users", "user_id", employee_id, "User (employee)")
    if err_resp is not None:
        return err_resp
    try:
        payload = {"project_id": project_id, "employee_id": employee_id}
        resp = supabase.table("project_assignments").insert(payload).execute()
        row, err = _one(resp, "Assignment")
        if err:
            return err
        return jsonify(row), 201
    except Exception as e:
        msg = str(e).lower()
        if "unique" in msg or "duplicate" in msg:
            return jsonify({"error": "Employee is already assigned to this project"}), 409
        return jsonify({"error": str(e)}), 500


@app.route('/api/projects/<int:project_id>/assignments/<int:assignment_id>', methods=['DELETE'])
def delete_assignment(project_id, assignment_id):
    err, status = _db()
    if err is not None:
        return err, status
    try:
        resp = supabase.table("project_assignments").delete().eq("assignment_id", assignment_id).eq("project_id", project_id).execute()
        data = getattr(resp, "data", None) or []
        if not data:
            return jsonify({"error": "Assignment not found"}), 404
        return jsonify({"message": "Assignment deleted"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ========== BACKLOG ITEMS ==========
@app.route('/api/projects/<int:project_id>/backlog', methods=['GET'])
def list_backlog(project_id):
    err, status = _db()
    if err is not None:
        return err, status
    err_resp = _require_exists("projects", "project_id", project_id, "Project")
    if err_resp is not None:
        return err_resp
    try:
        resp = supabase.table("backlog_items").select("*").eq("project_id", project_id).order("priority").order("backlog_item_id").execute()
        data = getattr(resp, "data", []) or []
        return jsonify({"backlog_items": data, "count": len(data)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/projects/<int:project_id>/backlog', methods=['POST'])
def create_backlog_item(project_id):
    err, status = _db()
    if err is not None:
        return err, status
    err_resp = _require_exists("projects", "project_id", project_id, "Project")
    if err_resp is not None:
        return err_resp
    data, err = _get_json(required_keys=["title"])
    if err is not None:
        return err
    priority = _int_or_none(data.get("priority"))
    if priority is None:
        priority = 0
    try:
        payload = {
            "project_id": project_id,
            "title": str(data["title"]).strip(),
            "description": (data.get("description") or "").strip() or None,
            "priority": priority,
        }
        resp = supabase.table("backlog_items").insert(payload).execute()
        row, err = _one(resp, "Backlog item")
        if err:
            return err
        return jsonify(row), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/backlog/<int:backlog_item_id>', methods=['GET'])
def get_backlog_item(backlog_item_id):
    err, status = _db()
    if err is not None:
        return err, status
    try:
        resp = supabase.table("backlog_items").select("*").eq("backlog_item_id", backlog_item_id).limit(1).execute()
        row, err = _one(resp, "Backlog item")
        if err:
            return err
        return jsonify(row)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/backlog/<int:backlog_item_id>', methods=['PUT'])
def update_backlog_item(backlog_item_id):
    err, status = _db()
    if err is not None:
        return err, status
    data = request.get_json(silent=True) or {}
    allowed = {"title", "description", "priority"}
    payload = {k: v for k, v in data.items() if k in allowed}
    if "priority" in payload and payload["priority"] is not None:
        p = _int_or_none(payload["priority"])
        if p is None:
            return jsonify({"error": "priority must be an integer"}), 400
        payload["priority"] = p
    if not payload:
        return jsonify({"error": "No valid fields to update"}), 400
    try:
        resp = supabase.table("backlog_items").update(payload).eq("backlog_item_id", backlog_item_id).execute()
        row, err = _one(resp, "Backlog item")
        if err:
            return err
        return jsonify(row)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/backlog/<int:backlog_item_id>', methods=['DELETE'])
def delete_backlog_item(backlog_item_id):
    err, status = _db()
    if err is not None:
        return err, status
    try:
        resp = supabase.table("backlog_items").delete().eq("backlog_item_id", backlog_item_id).execute()
        data = getattr(resp, "data", None) or []
        if not data:
            return jsonify({"error": "Backlog item not found"}), 404
        return jsonify({"message": "Backlog item deleted"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ========== SPRINTS ==========
@app.route('/api/projects/<int:project_id>/sprints', methods=['GET'])
def list_sprints(project_id):
    err, status = _db()
    if err is not None:
        return err, status
    err_resp = _require_exists("projects", "project_id", project_id, "Project")
    if err_resp is not None:
        return err_resp
    try:
        resp = supabase.table("sprints").select("*").eq("project_id", project_id).order("sprint_id").execute()
        data = getattr(resp, "data", []) or []
        return jsonify({"sprints": data, "count": len(data)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/projects/<int:project_id>/sprints', methods=['POST'])
def create_sprint(project_id):
    err, status = _db()
    if err is not None:
        return err, status
    err_resp = _require_exists("projects", "project_id", project_id, "Project")
    if err_resp is not None:
        return err_resp
    data, err = _get_json(required_keys=["sprint_name"])
    if err is not None:
        return err
    status_val = (data.get("status") or "PLANNED").upper()
    if status_val not in ("PLANNED", "ACTIVE", "COMPLETED"):
        return jsonify({"error": "status must be PLANNED, ACTIVE, or COMPLETED"}), 400
    try:
        payload = {
            "project_id": project_id,
            "sprint_name": str(data["sprint_name"]).strip(),
            "start_date": data.get("start_date"),
            "end_date": data.get("end_date"),
            "status": status_val,
        }
        resp = supabase.table("sprints").insert(payload).execute()
        row, err = _one(resp, "Sprint")
        if err:
            return err
        return jsonify(row), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/sprints/<int:sprint_id>', methods=['GET'])
def get_sprint(sprint_id):
    err, status = _db()
    if err is not None:
        return err, status
    try:
        resp = supabase.table("sprints").select("*").eq("sprint_id", sprint_id).limit(1).execute()
        row, err = _one(resp, "Sprint")
        if err:
            return err
        return jsonify(row)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/sprints/<int:sprint_id>', methods=['PUT'])
def update_sprint(sprint_id):
    err, status = _db()
    if err is not None:
        return err, status
    data = request.get_json(silent=True) or {}
    allowed = {"sprint_name", "start_date", "end_date", "status"}
    payload = {k: v for k, v in data.items() if k in allowed and v is not None}
    if "status" in payload:
        payload["status"] = (payload["status"] or "").upper()
        if payload["status"] not in ("PLANNED", "ACTIVE", "COMPLETED"):
            return jsonify({"error": "status must be PLANNED, ACTIVE, or COMPLETED"}), 400
    if not payload:
        return jsonify({"error": "No valid fields to update"}), 400
    try:
        resp = supabase.table("sprints").update(payload).eq("sprint_id", sprint_id).execute()
        row, err = _one(resp, "Sprint")
        if err:
            return err
        return jsonify(row)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/sprints/<int:sprint_id>', methods=['DELETE'])
def delete_sprint(sprint_id):
    err, status = _db()
    if err is not None:
        return err, status
    try:
        resp = supabase.table("sprints").delete().eq("sprint_id", sprint_id).execute()
        data = getattr(resp, "data", None) or []
        if not data:
            return jsonify({"error": "Sprint not found"}), 404
        return jsonify({"message": "Sprint deleted"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ========== TASKS ==========
@app.route('/api/sprints/<int:sprint_id>/tasks', methods=['GET'])
def list_tasks(sprint_id):
    err, status = _db()
    if err is not None:
        return err, status
    err_resp = _require_exists("sprints", "sprint_id", sprint_id, "Sprint")
    if err_resp is not None:
        return err_resp
    try:
        resp = supabase.table("tasks").select("*").eq("sprint_id", sprint_id).order("task_id").execute()
        data = getattr(resp, "data", []) or []
        return jsonify({"tasks": data, "count": len(data)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/sprints/<int:sprint_id>/tasks', methods=['POST'])
def create_task(sprint_id):
    err, status = _db()
    if err is not None:
        return err, status
    err_resp = _require_exists("sprints", "sprint_id", sprint_id, "Sprint")
    if err_resp is not None:
        return err_resp
    data, err = _get_json(required_keys=["title"])
    if err is not None:
        return err
    status_val = (data.get("status") or "TODO").upper().replace("-", "_")
    if status_val not in ("TODO", "IN_PROGRESS", "DONE"):
        return jsonify({"error": "status must be TODO, IN_PROGRESS, or DONE"}), 400
    assigned_id = _int_or_none(data.get("assigned_to_user_id"))
    if assigned_id is not None and not _exists("users", "user_id", assigned_id):
        return jsonify({"error": "assigned_to_user_id does not refer to an existing user"}), 400
    try:
        payload = {
            "sprint_id": sprint_id,
            "title": str(data["title"]).strip(),
            "description": (data.get("description") or "").strip() or None,
            "status": status_val,
        }
        if assigned_id is not None:
            payload["assigned_to_user_id"] = assigned_id
        resp = supabase.table("tasks").insert(payload).execute()
        row, err = _one(resp, "Task")
        if err:
            return err
        return jsonify(row), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/tasks/<int:task_id>', methods=['GET'])
def get_task(task_id):
    err, status = _db()
    if err is not None:
        return err, status
    try:
        resp = supabase.table("tasks").select("*").eq("task_id", task_id).limit(1).execute()
        row, err = _one(resp, "Task")
        if err:
            return err
        return jsonify(row)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    err, status = _db()
    if err is not None:
        return err, status
    data = request.get_json(silent=True) or {}
    allowed = {"title", "description", "status", "assigned_to_user_id"}
    payload = {k: v for k, v in data.items() if k in allowed}
    if "status" in payload:
        payload["status"] = (payload["status"] or "").upper().replace("-", "_")
        if payload["status"] not in ("TODO", "IN_PROGRESS", "DONE"):
            return jsonify({"error": "status must be TODO, IN_PROGRESS, or DONE"}), 400
    if "assigned_to_user_id" in payload and payload["assigned_to_user_id"] is not None:
        aid = _int_or_none(payload["assigned_to_user_id"])
        if aid is not None and not _exists("users", "user_id", aid):
            return jsonify({"error": "assigned_to_user_id does not refer to an existing user"}), 400
        payload["assigned_to_user_id"] = aid
    if not payload:
        return jsonify({"error": "No valid fields to update"}), 400
    try:
        resp = supabase.table("tasks").update(payload).eq("task_id", task_id).execute()
        row, err = _one(resp, "Task")
        if err:
            return err
        return jsonify(row)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    err, status = _db()
    if err is not None:
        return err, status
    try:
        resp = supabase.table("tasks").delete().eq("task_id", task_id).execute()
        data = getattr(resp, "data", None) or []
        if not data:
        return jsonify({"error": "Task not found"}), 404
        return jsonify({"message": "Task deleted"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/users/<int:user_id>/tasks', methods=['GET'])
def list_user_tasks(user_id):
    err, status = _db()
    if err is not None:
        return err, status
    try:
        resp = supabase.table("tasks").select("*").eq("assigned_to_user_id", user_id).order("task_id").execute()
        data = getattr(resp, "data", []) or []
        return jsonify({"tasks": data, "count": len(data)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ========== CHAT LOGS ==========
@app.route('/api/projects/<int:project_id>/chat', methods=['GET'])
def list_chat_logs(project_id):
    err, status = _db()
    if err is not None:
        return err, status
    err_resp = _require_exists("projects", "project_id", project_id, "Project")
    if err_resp is not None:
        return err_resp
    limit = min(max(request.args.get("limit", type=int) or 100, 500), 500)
    try:
        resp = supabase.table("chat_logs").select("*").eq("project_id", project_id).order("created_at").limit(limit).execute()
        data = getattr(resp, "data", []) or []
        return jsonify({"chat_logs": data, "count": len(data)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/projects/<int:project_id>/chat', methods=['POST'])
def create_chat_log(project_id):
    err, status = _db()
    if err is not None:
        return err, status
    err_resp = _require_exists("projects", "project_id", project_id, "Project")
    if err_resp is not None:
        return err_resp
    data, err = _get_json(required_keys=["user_id", "message", "sender_type"])
    if err is not None:
        return err
    if (data.get("sender_type") or "").upper() not in ("USER", "AI_BOT"):
        return jsonify({"error": "sender_type must be USER or AI_BOT"}), 400
    user_id = _int_or_none(data.get("user_id"))
    if user_id is None:
        return jsonify({"error": "user_id must be a valid integer"}), 400
    err_resp = _require_exists("users", "user_id", user_id, "User")
    if err_resp is not None:
        return err_resp
    try:
        payload = {
            "project_id": project_id,
            "user_id": user_id,
            "message": str(data["message"]).strip(),
            "sender_type": (data["sender_type"] or "").upper(),
        }
        resp = supabase.table("chat_logs").insert(payload).execute()
        row, err = _one(resp, "Chat log")
        if err:
            return err
        return jsonify(row), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ========== PERFORMANCE LOGS ==========
@app.route('/api/performance_logs', methods=['GET'])
def list_performance_logs():
    err, status = _db()
    if err is not None:
        return err, status
    user_id = request.args.get("user_id", type=int)
    task_id = request.args.get("task_id", type=int)
    try:
        q = supabase.table("performance_logs").select("*").order("performance_log_id")
        if user_id is not None:
            q = q.eq("user_id", user_id)
        if task_id is not None:
            q = q.eq("task_id", task_id)
        resp = q.execute()
        data = getattr(resp, "data", []) or []
        return jsonify({"performance_logs": data, "count": len(data)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/performance_logs', methods=['POST'])
def create_performance_log():
    err, status = _db()
    if err is not None:
        return err, status
    data, err = _get_json(required_keys=["user_id", "task_id"])
    if err is not None:
        return err
    user_id = _int_or_none(data.get("user_id"))
    task_id = _int_or_none(data.get("task_id"))
    if user_id is None or task_id is None:
        return jsonify({"error": "user_id and task_id must be valid integers"}), 400
    err_resp = _require_exists("users", "user_id", user_id, "User")
    if err_resp is not None:
        return err_resp
    err_resp = _require_exists("tasks", "task_id", task_id, "Task")
    if err_resp is not None:
        return err_resp
    try:
        payload = {
            "user_id": user_id,
            "task_id": task_id,
            "accuracy_score": data.get("accuracy_score"),
            "progress_percent": data.get("progress_percent"),
            "log_date": data.get("log_date"),
        }
        resp = supabase.table("performance_logs").insert(payload).execute()
        row, err = _one(resp, "Performance log")
        if err:
            return err
        return jsonify(row), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/performance_logs/<int:performance_log_id>', methods=['GET'])
def get_performance_log(performance_log_id):
    err, status = _db()
    if err is not None:
        return err, status
    try:
        resp = supabase.table("performance_logs").select("*").eq("performance_log_id", performance_log_id).limit(1).execute()
        row, err = _one(resp, "Performance log")
        if err:
            return err
        return jsonify(row)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/performance_logs/<int:performance_log_id>', methods=['PUT'])
def update_performance_log(performance_log_id):
    err, status = _db()
    if err is not None:
        return err, status
    data = request.get_json(silent=True) or {}
    allowed = {"accuracy_score", "progress_percent", "log_date"}
    payload = {k: v for k, v in data.items() if k in allowed}
    if not payload:
        return jsonify({"error": "No valid fields to update"}), 400
    try:
        resp = supabase.table("performance_logs").update(payload).eq("performance_log_id", performance_log_id).execute()
        row, err = _one(resp, "Performance log")
        if err:
            return err
        return jsonify(row)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/performance_logs/<int:performance_log_id>', methods=['DELETE'])
def delete_performance_log(performance_log_id):
    err, status = _db()
    if err is not None:
        return err, status
    try:
        resp = supabase.table("performance_logs").delete().eq("performance_log_id", performance_log_id).execute()
        data = getattr(resp, "data", None) or []
        if not data:
            return jsonify({"error": "Performance log not found"}), 404
        return jsonify({"message": "Performance log deleted"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/users/<int:user_id>/performance', methods=['GET'])
def list_user_performance(user_id):
    err, status = _db()
    if err is not None:
        return err, status
    try:
        resp = supabase.table("performance_logs").select("*").eq("user_id", user_id).order("log_date").execute()
        data = getattr(resp, "data", []) or []
        return jsonify({"performance_logs": data, "count": len(data)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify(
        {
            "status": "healthy",
            "service": "Scrum Master API",
            "supabase_configured": bool(supabase),
            "cors_origins": cors_origins,
        }
    )


@app.route("/api/supabase/ping", methods=["GET"])
def supabase_ping():
    """
    Verifies the Supabase client is configured.
    If SUPABASE_PING_TABLE is set, it also performs a real DB query.
    """
    if not supabase:
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "Supabase is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_ANON_KEY).",
                }
            ),
            500,
        )

    # Option A: If frontend sends a JWT, validate it against Supabase Auth.
    auth_header = request.headers.get("Authorization", "").strip()
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        try:
            user = supabase.auth.get_user(token)
            return jsonify({"ok": True, "mode": "jwt", "user": user.user.model_dump() if user and user.user else None})
        except Exception as e:
            return jsonify({"ok": False, "mode": "jwt", "error": str(e)}), 500

    # Option B: Perform a real DB query if a table is configured.
    table = app.config.get("SUPABASE_PING_TABLE") or ""
    if table:
        try:
            # This hits the PostgREST endpoint (database) and will fail if:
            # - table doesn't exist, or
            # - key lacks access due to RLS / permissions, or
            # - network / URL is wrong
            resp = supabase.table(table).select("*").limit(1).execute()
            rows = resp.data if hasattr(resp, "data") else None
            return jsonify(
                {
                    "ok": True,
                    "mode": "table_select",
                    "table": table,
                    "row_count_returned": len(rows) if isinstance(rows, list) else None,
                }
            )
        except Exception as e:
            return jsonify({"ok": False, "mode": "table_select", "table": table, "error": str(e)}), 500

    # Fallback: just confirm client is initialized.
    return jsonify({"ok": True, "mode": "client_initialized", "hint": "Set SUPABASE_PING_TABLE to run a DB query."})

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    ok, msg = _check_supabase_db_connection()
    print(msg, flush=True)
    app.run(host='0.0.0.0', port=port, debug=app.config['DEBUG'])
