# AI-Powered Virtual Scrum Master – Backend

Production-ready Flask API with **clean architecture**, **JWT auth**, and **role-based access (ADMIN / EMPLOYEE)**.

## Structure

```
backend/
  app/
    config.py           # Config from env
    __init__.py         # create_app(), blueprints, CORS
    middleware/
      auth.py           # require_auth, require_admin, require_employee, JWT
    routes/
      auth.py           # register, login, me
      users.py          # CRUD (Admin)
      projects.py       # projects + assignments
      backlog.py        # backlog by project + by id
      sprints.py        # sprints by project + by id
      tasks.py          # tasks by sprint + by id
      performance.py    # log, me, user, project
      chat.py           # send, list by project
      dashboard.py      # admin, employee
    services/
      db.py             # Supabase client, one(), exists()
      auth_service.py
      user_service.py
      project_service.py
      backlog_service.py
      sprint_service.py
      task_service.py
      performance_service.py
      chat_service.py   # AI stub + keyword task updates
      dashboard_service.py
    utils/
      response.py       # api_success, api_error
      validators.py
  main.py               # Entry point
  requirements.txt
  .env.example
  API_DOCS.md           # Example request/response payloads
```

## Run

1. Copy `.env.example` to `.env` and set:
   - `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (or `SUPABASE_ANON_KEY`)
   - `JWT_SECRET_KEY` (or it falls back to `SECRET_KEY`)

2. Install and start:
   ```bash
   pip install -r requirements.txt
   python main.py
   ```

3. Open `http://localhost:5000` for the API index and `http://localhost:5000/health` for health.

## Auth flow

- **POST /auth/register** – Create user (body: full_name, email, password, role). Returns `user` + `token`.
- **POST /auth/login** – Body: email, password. Returns `user` + `token`.
- **GET /auth/me** – Header: `Authorization: Bearer <token>`. Returns current user.

Use `Authorization: Bearer <token>` on all protected routes.

## Roles

- **ADMIN**: Full access (users, projects, assignments, backlog, sprints, tasks, performance, chat, admin dashboard).
- **EMPLOYEE**: Only assigned projects, own tasks, own performance, chat in assigned projects, employee dashboard.

## Response format

- Success: `{ "success": true, "data": ..., "message": "..." }`
- Error: `{ "success": false, "message": "..." }`

See **API_DOCS.md** for all endpoints and example payloads.

## Chat & AI

- **POST /chat/send** – Body: `project_id`, `message`. Stores user message, runs stub `ai_generate_response()`, detects keywords (e.g. "task 5 done", "started", "blocked") and updates task status, stores AI message, returns both. Replace `ai_generate_response()` in `app/services/chat_service.py` with real LLM integration when ready.

## Legacy

The previous single-file API is in `app.py`. Use **main.py** + **app/** for the new backend.
