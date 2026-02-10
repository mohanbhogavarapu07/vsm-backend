# API Documentation

Base URL: `http://localhost:5000`

**Swagger UI:** Open [http://localhost:5000/apidocs](http://localhost:5000/apidocs) in a browser to explore and try all endpoints. Use **Authorize** to set your JWT (e.g. `Bearer <token>`).

All successful responses: `{ "success": true, "data": ..., "message": "..." }`  
All errors: `{ "success": false, "message": "..." }`

Use header: `Authorization: Bearer <token>` for protected routes.

---

## Auth

### POST /auth/register
**Body:**
```json
{
  "full_name": "John Doe",
  "email": "john@example.com",
  "password": "secret123",
  "role": "ADMIN"
}
```
**Response (201):**
```json
{
  "success": true,
  "data": {
    "user": { "user_id": 1, "full_name": "John Doe", "email": "john@example.com", "role": "ADMIN", "created_at": "...", "updated_at": "..." },
    "token": "eyJ..."
  },
  "message": "Registered successfully"
}
```

### POST /auth/login
**Body:**
```json
{ "email": "john@example.com", "password": "secret123" }
```
**Response (200):**
```json
{
  "success": true,
  "data": {
    "user": { "user_id": 1, "full_name": "John Doe", "email": "john@example.com", "role": "ADMIN", ... },
    "token": "eyJ..."
  },
  "message": "Login successful"
}
```

### GET /auth/me
**Headers:** `Authorization: Bearer <token>`
**Response (200):** `{ "success": true, "data": { "user_id": 1, "full_name": "...", "email": "...", "role": "ADMIN", ... } }`

---

## Users (Admin only)

- **GET /users** – List all (optional `?role=EMPLOYEE`)
- **GET /users/{id}** – Get one
- **PUT /users/{id}** – Update (body: full_name, email, password, role)
- **DELETE /users/{id}** – Delete

---

## Projects

- **POST /projects** (Admin) – Body: project_name, created_by_admin_id, description?, start_date?, end_date?
- **GET /projects** – Admin: all; Employee: only assigned
- **GET /projects/{id}**
- **PUT /projects/{id}** (Admin) – Body: project_name?, description?, start_date?, end_date?
- **DELETE /projects/{id}** (Admin)
- **POST /projects/{id}/assign** (Admin) – Body: { "employee_id": 2 }
- **GET /projects/{id}/members** (Admin)
- **DELETE /projects/{id}/members/{user_id}** (Admin)

---

## Backlog

- **POST /projects/{id}/backlog** (Admin) – Body: title, description?, priority?
- **GET /projects/{id}/backlog**
- **PUT /backlog/{id}** – Body: title?, description?, priority?
- **DELETE /backlog/{id}** (Admin)

---

## Sprints

- **POST /projects/{id}/sprints** (Admin) – Body: sprint_name, start_date?, end_date?, status?
- **GET /projects/{id}/sprints**
- **GET /sprints/{id}**
- **PUT /sprints/{id}** (Admin) – Body: sprint_name?, start_date?, end_date?, status?
- **DELETE /sprints/{id}** (Admin)

---

## Tasks

- **POST /sprints/{id}/tasks** (Admin) – Body: title, description?, status?, assigned_to_user_id?
- **GET /sprints/{id}/tasks** – Admin: all; Employee: only own tasks in that sprint
- **GET /tasks** – Admin: all; Employee: only assigned
- **GET /tasks/{id}**
- **PUT /tasks/{id}** – Employee can update only own; Admin any. Body: title?, description?, status?, assigned_to_user_id? (Admin only)
- **PUT /tasks/{id}/status** – Body: { "status": "IN_PROGRESS" }
- **DELETE /tasks/{id}** (Admin)

---

## Performance

- **POST /performance/log** (Admin) – Body: user_id, task_id, accuracy_score?, progress_percent?, log_date?
- **GET /performance/me** – Current user's logs
- **GET /performance/user/{id}** (Admin)
- **GET /performance/project/{id}** (Admin)

---

## Chat & AI

- **POST /chat/send** – Body: { "project_id": 1, "message": "Task 5 is done" }  
  Stores user message, runs AI stub, may update task status from keywords (e.g. "task 5 done" → mark task 5 DONE), stores AI reply, returns both.
- **GET /chat/project/{project_id}** – Optional `?limit=100`

---

## Dashboards

- **GET /dashboard/admin** (Admin) – total_projects, total_employees, sprint_status_summary, task_status_counts, bottlenecks_count, performance_averages
- **GET /dashboard/employee** – my_projects, my_tasks, my_performance, summary
