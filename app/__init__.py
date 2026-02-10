"""
Flask application factory. Creates app, loads config, registers blueprints, CORS, and Swagger UI.
"""
from flask import Flask
from flask_cors import CORS
from flasgger import Swagger

from app.config import Config
from app.swagger_spec import SWAGGER_TEMPLATE


def create_app(config_object=None):
    app = Flask(__name__)
    app.config.from_object(config_object or Config)

    # CORS (include Swagger UI and spec endpoints)
    # Auth routes need explicit allow_headers so cross-origin clients can send Authorization
    CORS(
        app,
        resources={
            r"/auth/*": {
                "origins": Config.CORS_ORIGINS,
                "allow_headers": ["Content-Type", "Authorization", "X-Access-Token"],
            },
            r"/users/*": {"origins": Config.CORS_ORIGINS, "allow_headers": ["Content-Type", "Authorization", "X-Access-Token"]},
            r"/projects/*": {"origins": Config.CORS_ORIGINS, "allow_headers": ["Content-Type", "Authorization", "X-Access-Token"]},
            r"/backlog/*": {"origins": Config.CORS_ORIGINS, "allow_headers": ["Content-Type", "Authorization", "X-Access-Token"]},
            r"/sprints/*": {"origins": Config.CORS_ORIGINS, "allow_headers": ["Content-Type", "Authorization", "X-Access-Token"]},
            r"/tasks/*": {"origins": Config.CORS_ORIGINS, "allow_headers": ["Content-Type", "Authorization", "X-Access-Token"]},
            r"/performance/*": {"origins": Config.CORS_ORIGINS, "allow_headers": ["Content-Type", "Authorization", "X-Access-Token"]},
            r"/chat/*": {"origins": Config.CORS_ORIGINS, "allow_headers": ["Content-Type", "Authorization", "X-Access-Token"]},
            r"/dashboard/*": {"origins": Config.CORS_ORIGINS, "allow_headers": ["Content-Type", "Authorization", "X-Access-Token"]},
            r"/apidocs/*": {"origins": Config.CORS_ORIGINS},
            r"/apispec_1.json": {"origins": Config.CORS_ORIGINS},
        },
        supports_credentials=True,
    )

    # Swagger UI at /apidocs (Flasgger default)
    Swagger(app, template=SWAGGER_TEMPLATE)

    # Supabase key: prefer service_role JWT
    _sr = (app.config.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    _anon = (app.config.get("SUPABASE_ANON_KEY") or "").strip()
    if _sr and _sr.startswith("eyJ") and _sr.count(".") >= 2:
        app.config["SUPABASE_KEY"] = _sr
    elif _anon and _anon.startswith("eyJ") and _anon.count(".") >= 2:
        app.config["SUPABASE_KEY"] = _anon
    else:
        app.config["SUPABASE_KEY"] = _sr or _anon

    # Blueprints
    from app.routes.auth import bp as auth_bp
    from app.routes.users import bp as users_bp
    from app.routes.projects import bp as projects_bp
    from app.routes.backlog import bp as backlog_bp, backlog_id_bp
    from app.routes.sprints import bp as sprints_bp, sprint_id_bp
    from app.routes.tasks import bp as sprint_tasks_bp, tasks_bp
    from app.routes.performance import bp as performance_bp
    from app.routes.chat import bp as chat_bp
    from app.routes.dashboard import bp as dashboard_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(backlog_bp)
    app.register_blueprint(backlog_id_bp)
    app.register_blueprint(sprints_bp)
    app.register_blueprint(sprint_id_bp)
    app.register_blueprint(sprint_tasks_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(performance_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(dashboard_bp)

    @app.route("/")
    def index():
        return {
            "message": "AI-Powered Virtual Scrum Master API",
            "version": "1.0.0",
            "swagger_ui": "http://localhost:5000/apidocs/",
            "docs": {
                "auth": "POST /auth/register, POST /auth/login, GET /auth/me",
                "users": "GET/PUT/DELETE /users, /users/{id} (Admin)",
                "projects": "GET/POST/PUT/DELETE /projects, /projects/{id}/assign, /projects/{id}/members",
                "backlog": "GET/POST /projects/{id}/backlog, PUT/DELETE /backlog/{id}",
                "sprints": "GET/POST /projects/{id}/sprints, GET/PUT/DELETE /sprints/{id}",
                "tasks": "GET/POST /sprints/{id}/tasks, GET/PUT/DELETE /tasks/{id}, PUT /tasks/{id}/status",
                "performance": "POST /performance/log, GET /performance/me, /performance/user/{id}, /performance/project/{id}",
                "chat": "POST /chat/send, GET /chat/project/{project_id}",
                "dashboard": "GET /dashboard/admin, GET /dashboard/employee",
            },
        }

    @app.route("/health", methods=["GET"])
    def health():
        return {"success": True, "message": "OK", "service": "Scrum Master API"}

    @app.errorhandler(405)
    def method_not_allowed(e):
        from flask import request
        path = request.path if request else ""
        msg = "The method is not allowed for the requested URL."
        if path.startswith("/projects/") and "/backlog" not in path and "/assign" not in path and "/members" not in path:
            parts = path.strip("/").split("/")
            if len(parts) >= 2 and parts[1].isdigit():
                msg = f"POST {path} is not allowed. To create a backlog item use POST /projects/{parts[1]}/backlog with body: {{\"title\": \"...\", \"description\": \"...\", \"priority\": 0}}"
        from app.utils.response import api_error
        return api_error(msg, 405)

    @app.errorhandler(404)
    def not_found(e):
        from flask import request
        path = request.path if request else ""
        msg = "The requested resource was not found."
        if "{" in path and "}" in path:
            msg = f"Invalid path: '{path}'. Replace placeholders with actual IDs (e.g. GET /users/1 not /users/{{user_id}})."
        from app.utils.response import api_error
        return api_error(msg, 404)

    return app
