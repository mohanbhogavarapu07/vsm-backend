"""Chat: POST /chat/send, GET /chat/project/{project_id}. AI stub + keyword task updates."""
from flask import Blueprint, request, g
from app.middleware.auth import require_auth_admin_or_employee
from app.services import chat_service
from app.utils.response import api_success, api_error
from app.utils.validators import required_keys

bp = Blueprint("chat", __name__, url_prefix="/chat")


@bp.route("/send", methods=["POST"])
@require_auth_admin_or_employee
def send():
    """Body: project_id, message. Stores user message, generates AI response, optional task updates."""
    data = request.get_json(silent=True) or {}
    err = required_keys(data, ["project_id", "message"])
    if err:
        return api_error(err, 400)
    project_id = data.get("project_id")
    try:
        project_id = int(project_id)
    except (TypeError, ValueError):
        return api_error("project_id must be a valid integer", 400)
    is_admin = g.current_user.get("role") == "ADMIN"
    result, err = chat_service.send_message(project_id, g.current_user["user_id"], data.get("message"), is_admin=is_admin)
    if err:
        return api_error(err, 404 if "not found" in err else 500)
    return api_success(result, message="Message sent", status=201)


@bp.route("/project/<int:project_id>", methods=["GET"])
@require_auth_admin_or_employee
def list_chat(project_id):
    limit = request.args.get("limit", type=int) or 100
    is_admin = g.current_user.get("role") == "ADMIN"
    data, err = chat_service.list_chat(project_id, g.current_user["user_id"], limit=limit, is_admin=is_admin)
    if err:
        return api_error(err, 404 if "not found" in err else 500)
    return api_success({"chat_logs": data, "count": len(data)})
