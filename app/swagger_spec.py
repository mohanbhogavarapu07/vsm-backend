"""
OpenAPI (Swagger 2.0) specification for AI-Powered Virtual Scrum Master API.
Used by Flasgger to serve Swagger UI at /apidocs.
"""

SWAGGER_TEMPLATE = {
    "swagger": "2.0",
    "info": {
        "title": "AI-Powered Virtual Scrum Master API",
        "description": "REST API with JWT auth and role-based access (ADMIN / EMPLOYEE). "
                        "Use **Authorize** to set Bearer token after login.",
        "version": "1.0.0",
        "contact": {"name": "Scrum Master API"},
    },
    "host": "localhost:5000",
    "basePath": "/",
    "schemes": ["http", "https"],
    "consumes": ["application/json"],
    "produces": ["application/json"],
    "securityDefinitions": {
        "Bearer": {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization",
            "description": "JWT token. Example: Bearer &lt;your_token&gt;",
        }
    },
    "security": [{"Bearer": []}],
    "tags": [
        {"name": "Auth", "description": "Register, login, current user"},
        {"name": "Users", "description": "User CRUD (Admin only)"},
        {"name": "Projects", "description": "Projects and assignments"},
        {"name": "Backlog", "description": "Backlog items"},
        {"name": "Sprints", "description": "Sprints"},
        {"name": "Tasks", "description": "Tasks"},
        {"name": "Performance", "description": "Performance logs"},
        {"name": "Chat", "description": "Chat and AI Scrum Master"},
        {"name": "Dashboard", "description": "Admin and employee dashboards"},
    ],
    "paths": {
        "/auth/register": {
            "post": {
                "tags": ["Auth"],
                "summary": "Register a new user",
                "security": [],
                "parameters": [{
                    "in": "body",
                    "name": "body",
                    "required": True,
                    "schema": {
                        "type": "object",
                        "required": ["full_name", "email", "password", "role"],
                        "properties": {
                            "full_name": {"type": "string", "example": "John Doe"},
                            "email": {"type": "string", "example": "john@example.com"},
                            "password": {"type": "string", "example": "secret123"},
                            "role": {"type": "string", "enum": ["ADMIN", "EMPLOYEE"]},
                        },
                    },
                }],
                "responses": {
                    "201": {"description": "Registered successfully; returns user and token"},
                    "400": {"description": "Validation error or email already exists"},
                },
            },
        },
        "/auth/login": {
            "post": {
                "tags": ["Auth"],
                "summary": "Login and get JWT",
                "security": [],
                "parameters": [{
                    "in": "body",
                    "name": "body",
                    "required": True,
                    "schema": {
                        "type": "object",
                        "required": ["email", "password"],
                        "properties": {
                            "email": {"type": "string"},
                            "password": {"type": "string"},
                        },
                    },
                }],
                "responses": {
                    "200": {"description": "Returns user and token"},
                    "401": {"description": "Invalid credentials"},
                },
            },
        },
        "/auth/me": {
            "get": {
                "tags": ["Auth"],
                "summary": "Get current user from JWT",
                "responses": {"200": {"description": "Current user"}},
            },
        },
        "/users": {
            "get": {
                "tags": ["Users"],
                "summary": "List all users (Admin)",
                "parameters": [{"in": "query", "name": "role", "type": "string", "enum": ["ADMIN", "EMPLOYEE"]}],
                "responses": {"200": {"description": "List of users"}},
            },
        },
        "/users/{user_id}": {
            "get": {"tags": ["Users"], "summary": "Get user by ID (Admin)", "parameters": [{"in": "path", "name": "user_id", "type": "integer", "required": True, "example": 1}], "responses": {"200": {"description": "User"}, "404": {"description": "Not found"}}},
            "put": {
                "tags": ["Users"],
                "summary": "Update user (Admin)",
                "parameters": [
                    {"in": "path", "name": "user_id", "type": "integer", "required": True, "example": 1},
                    {"in": "body", "name": "body", "schema": {"type": "object", "properties": {"full_name": {"type": "string"}, "email": {"type": "string"}, "password": {"type": "string"}, "role": {"type": "string", "enum": ["ADMIN", "EMPLOYEE"]}}}},
                ],
                "responses": {"200": {"description": "Updated user"}},
            },
            "delete": {"tags": ["Users"], "summary": "Delete user (Admin)", "parameters": [{"in": "path", "name": "user_id", "type": "integer", "required": True, "example": 1}], "responses": {"200": {"description": "Deleted"}}},
        },
        "/projects": {
            "get": {"tags": ["Projects"], "summary": "List projects (Admin: all, Employee: assigned only)", "responses": {"200": {"description": "List of projects"}}},
            "post": {
                "tags": ["Projects"],
                "summary": "Create project (Admin)",
                "parameters": [{
                    "in": "body",
                    "name": "body",
                    "required": True,
                    "schema": {"type": "object", "required": ["project_name", "created_by_admin_id"], "properties": {"project_name": {"type": "string"}, "description": {"type": "string"}, "created_by_admin_id": {"type": "integer"}, "start_date": {"type": "string", "format": "date-time"}, "end_date": {"type": "string", "format": "date-time"}}},
                }],
                "responses": {"201": {"description": "Project created"}},
            },
        },
        "/projects/{project_id}": {
            "get": {"tags": ["Projects"], "summary": "Get project", "parameters": [{"in": "path", "name": "project_id", "type": "integer", "required": True}], "responses": {"200": {"description": "Project"}}},
            "put": {
                "tags": ["Projects"],
                "summary": "Update project (Admin)",
                "parameters": [
                    {"in": "path", "name": "project_id", "type": "integer", "required": True},
                    {"in": "body", "name": "body", "schema": {"type": "object", "properties": {"project_name": {"type": "string"}, "description": {"type": "string"}, "start_date": {"type": "string"}, "end_date": {"type": "string"}}}},
                ],
                "responses": {"200": {"description": "Updated project"}},
            },
            "delete": {"tags": ["Projects"], "summary": "Delete project (Admin)", "parameters": [{"in": "path", "name": "project_id", "type": "integer", "required": True}], "responses": {"200": {"description": "Deleted"}}},
        },
        "/projects/{project_id}/assign": {
            "post": {
                "tags": ["Projects"],
                "summary": "Assign employee(s) to project (Admin)",
                "parameters": [
                    {"in": "path", "name": "project_id", "type": "integer", "required": True, "example": 1},
                    {"in": "body", "name": "body", "required": True, "schema": {"type": "object", "properties": {"employee_id": {"type": "integer", "description": "Single employee (use employee_ids for multiple)"}, "employee_ids": {"type": "array", "items": {"type": "integer"}, "description": "Multiple employees", "example": [1, 2, 3]}}}},
                ],
                "responses": {"201": {"description": "Assigned"}},
            },
        },
        "/projects/{project_id}/members": {
            "get": {"tags": ["Projects"], "summary": "List project members (Admin)", "parameters": [{"in": "path", "name": "project_id", "type": "integer", "required": True}], "responses": {"200": {"description": "List of members"}}},
        },
        "/projects/{project_id}/members/{user_id}": {
            "delete": {"tags": ["Projects"], "summary": "Remove member (Admin)", "parameters": [{"in": "path", "name": "project_id", "type": "integer", "required": True}, {"in": "path", "name": "user_id", "type": "integer", "required": True}], "responses": {"200": {"description": "Removed"}}},
        },
        "/projects/{project_id}/backlog": {
            "get": {"tags": ["Backlog"], "summary": "List backlog items", "parameters": [{"in": "path", "name": "project_id", "type": "integer", "required": True}], "responses": {"200": {"description": "List of backlog items"}}},
            "post": {
                "tags": ["Backlog"],
                "summary": "Create backlog item (Admin)",
                "parameters": [
                    {"in": "path", "name": "project_id", "type": "integer", "required": True},
                    {"in": "body", "name": "body", "required": True, "schema": {"type": "object", "required": ["title"], "properties": {"title": {"type": "string"}, "description": {"type": "string"}, "priority": {"type": "integer"}}}},
                ],
                "responses": {"201": {"description": "Backlog item created"}},
            },
        },
        "/backlog/{backlog_item_id}": {
            "put": {
                "tags": ["Backlog"],
                "summary": "Update backlog item",
                "parameters": [
                    {"in": "path", "name": "backlog_item_id", "type": "integer", "required": True},
                    {"in": "body", "name": "body", "schema": {"type": "object", "properties": {"title": {"type": "string"}, "description": {"type": "string"}, "priority": {"type": "integer"}}}},
                ],
                "responses": {"200": {"description": "Updated"}},
            },
            "delete": {"tags": ["Backlog"], "summary": "Delete backlog item (Admin)", "parameters": [{"in": "path", "name": "backlog_item_id", "type": "integer", "required": True}], "responses": {"200": {"description": "Deleted"}}},
        },
        "/projects/{project_id}/sprints": {
            "get": {"tags": ["Sprints"], "summary": "List sprints", "parameters": [{"in": "path", "name": "project_id", "type": "integer", "required": True}], "responses": {"200": {"description": "List of sprints"}}},
            "post": {
                "tags": ["Sprints"],
                "summary": "Create sprint (Admin)",
                "parameters": [
                    {"in": "path", "name": "project_id", "type": "integer", "required": True},
                    {"in": "body", "name": "body", "required": True, "schema": {"type": "object", "required": ["sprint_name"], "properties": {"sprint_name": {"type": "string"}, "start_date": {"type": "string", "format": "date"}, "end_date": {"type": "string", "format": "date"}, "status": {"type": "string", "enum": ["PLANNED", "ACTIVE", "COMPLETED"]}}}},
                ],
                "responses": {"201": {"description": "Sprint created"}},
            },
        },
        "/sprints/{sprint_id}": {
            "get": {"tags": ["Sprints"], "summary": "Get sprint", "parameters": [{"in": "path", "name": "sprint_id", "type": "integer", "required": True}], "responses": {"200": {"description": "Sprint"}}},
            "put": {
                "tags": ["Sprints"],
                "summary": "Update sprint (Admin)",
                "parameters": [
                    {"in": "path", "name": "sprint_id", "type": "integer", "required": True},
                    {"in": "body", "name": "body", "schema": {"type": "object", "properties": {"sprint_name": {"type": "string"}, "start_date": {"type": "string"}, "end_date": {"type": "string"}, "status": {"type": "string", "enum": ["PLANNED", "ACTIVE", "COMPLETED"]}}}},
                ],
                "responses": {"200": {"description": "Updated"}},
            },
            "delete": {"tags": ["Sprints"], "summary": "Delete sprint (Admin)", "parameters": [{"in": "path", "name": "sprint_id", "type": "integer", "required": True}], "responses": {"200": {"description": "Deleted"}}},
        },
        "/sprints/{sprint_id}/tasks": {
            "get": {"tags": ["Tasks"], "summary": "List tasks in sprint", "parameters": [{"in": "path", "name": "sprint_id", "type": "integer", "required": True}], "responses": {"200": {"description": "List of tasks"}}},
            "post": {
                "tags": ["Tasks"],
                "summary": "Create task (Admin)",
                "parameters": [
                    {"in": "path", "name": "sprint_id", "type": "integer", "required": True},
                    {"in": "body", "name": "body", "required": True, "schema": {"type": "object", "required": ["title"], "properties": {"title": {"type": "string"}, "description": {"type": "string"}, "status": {"type": "string", "enum": ["TODO", "IN_PROGRESS", "DONE"]}, "assigned_to_user_id": {"type": "integer"}}}},
                ],
                "responses": {"201": {"description": "Task created"}},
            },
        },
        "/tasks": {
            "get": {"tags": ["Tasks"], "summary": "List tasks (Admin: all, Employee: assigned only)", "responses": {"200": {"description": "List of tasks"}}},
        },
        "/tasks/{task_id}": {
            "get": {"tags": ["Tasks"], "summary": "Get task", "parameters": [{"in": "path", "name": "task_id", "type": "integer", "required": True}], "responses": {"200": {"description": "Task"}}},
            "put": {
                "tags": ["Tasks"],
                "summary": "Update task (Employee: own only)",
                "parameters": [
                    {"in": "path", "name": "task_id", "type": "integer", "required": True},
                    {"in": "body", "name": "body", "schema": {"type": "object", "properties": {"title": {"type": "string"}, "description": {"type": "string"}, "status": {"type": "string", "enum": ["TODO", "IN_PROGRESS", "DONE"]}, "assigned_to_user_id": {"type": "integer"}}}},
                ],
                "responses": {"200": {"description": "Updated"}},
            },
            "delete": {"tags": ["Tasks"], "summary": "Delete task (Admin)", "parameters": [{"in": "path", "name": "task_id", "type": "integer", "required": True}], "responses": {"200": {"description": "Deleted"}}},
        },
        "/tasks/{task_id}/status": {
            "put": {
                "tags": ["Tasks"],
                "summary": "Update task status",
                "parameters": [
                    {"in": "path", "name": "task_id", "type": "integer", "required": True},
                    {"in": "body", "name": "body", "required": True, "schema": {"type": "object", "required": ["status"], "properties": {"status": {"type": "string", "enum": ["TODO", "IN_PROGRESS", "DONE"]}}}},
                ],
                "responses": {"200": {"description": "Status updated"}},
            },
        },
        "/performance/log": {
            "post": {
                "tags": ["Performance"],
                "summary": "Create performance log (Admin). Also: POST /performance/logs",
                "parameters": [{"in": "body", "name": "body", "required": True, "schema": {"type": "object", "required": ["user_id", "task_id"], "properties": {"user_id": {"type": "integer"}, "task_id": {"type": "integer"}, "accuracy_score": {"type": "number"}, "progress_percent": {"type": "number"}, "log_date": {"type": "string", "format": "date"}}}},
                ],
                "responses": {"201": {"description": "Log created"}},
            },
        },
        "/performance/logs": {
            "post": {
                "tags": ["Performance"],
                "summary": "Create performance log (Admin). Alias for /performance/log",
                "parameters": [{"in": "body", "name": "body", "required": True, "schema": {"type": "object", "required": ["user_id", "task_id"], "properties": {"user_id": {"type": "integer"}, "task_id": {"type": "integer"}, "accuracy_score": {"type": "number"}, "progress_percent": {"type": "number"}, "log_date": {"type": "string", "format": "date"}}}},
                ],
                "responses": {"201": {"description": "Log created"}},
            },
        },
        "/performance/me": {
            "get": {"tags": ["Performance"], "summary": "My performance logs", "responses": {"200": {"description": "List of performance logs"}}},
        },
        "/performance/user/{user_id}": {
            "get": {"tags": ["Performance"], "summary": "Performance logs by user (Admin)", "parameters": [{"in": "path", "name": "user_id", "type": "integer", "required": True}], "responses": {"200": {"description": "List of logs"}}},
        },
        "/performance/project/{project_id}": {
            "get": {"tags": ["Performance"], "summary": "Performance logs by project (Admin)", "parameters": [{"in": "path", "name": "project_id", "type": "integer", "required": True}], "responses": {"200": {"description": "List of logs"}}},
        },
        "/chat/send": {
            "post": {
                "tags": ["Chat"],
                "summary": "Send message (stores user + AI response, may update tasks from keywords)",
                "parameters": [{"in": "body", "name": "body", "required": True, "schema": {"type": "object", "required": ["project_id", "message"], "properties": {"project_id": {"type": "integer"}, "message": {"type": "string"}}}},
                ],
                "responses": {"201": {"description": "User and AI messages + task_updates"}},
            },
        },
        "/chat/project/{project_id}": {
            "get": {"tags": ["Chat"], "summary": "List chat logs for project", "parameters": [{"in": "path", "name": "project_id", "type": "integer", "required": True}, {"in": "query", "name": "limit", "type": "integer"}], "responses": {"200": {"description": "List of chat logs"}}},
        },
        "/dashboard/admin": {
            "get": {"tags": ["Dashboard"], "summary": "Admin dashboard (totals, sprint/task status, bottlenecks, performance)", "responses": {"200": {"description": "Dashboard data"}}},
        },
        "/dashboard/employee": {
            "get": {"tags": ["Dashboard"], "summary": "Employee dashboard (my projects, tasks, performance)", "responses": {"200": {"description": "Dashboard data"}}},
        },
        "/health": {
            "get": {"tags": [], "summary": "Health check", "security": [], "responses": {"200": {"description": "OK"}}},
        },
    },
}
