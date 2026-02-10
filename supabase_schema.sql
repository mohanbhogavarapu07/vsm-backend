-- Scrum Master schema for Supabase (run in SQL Editor)
-- Tables: users, projects, project_assignments, backlog_items, chat_logs, sprints, tasks, performance_logs

-- 1. USERS
CREATE TABLE IF NOT EXISTS public.users (
  user_id BIGSERIAL PRIMARY KEY,
  full_name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('ADMIN', 'EMPLOYEE')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. PROJECTS
CREATE TABLE IF NOT EXISTS public.projects (
  project_id BIGSERIAL PRIMARY KEY,
  project_name TEXT NOT NULL,
  description TEXT,
  created_by_admin_id BIGINT NOT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
  start_date TIMESTAMPTZ,
  end_date TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. PROJECT_ASSIGNMENTS (many-to-many: users <-> projects)
CREATE TABLE IF NOT EXISTS public.project_assignments (
  assignment_id BIGSERIAL PRIMARY KEY,
  project_id BIGINT NOT NULL REFERENCES public.projects(project_id) ON DELETE CASCADE,
  employee_id BIGINT NOT NULL REFERENCES public.users(user_id) ON DELETE CASCADE,
  assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(project_id, employee_id)
);

-- 4. BACKLOG_ITEMS
CREATE TABLE IF NOT EXISTS public.backlog_items (
  backlog_item_id BIGSERIAL PRIMARY KEY,
  project_id BIGINT NOT NULL REFERENCES public.projects(project_id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  description TEXT,
  priority INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. CHAT_LOGS
CREATE TABLE IF NOT EXISTS public.chat_logs (
  chat_log_id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES public.users(user_id) ON DELETE CASCADE,
  project_id BIGINT NOT NULL REFERENCES public.projects(project_id) ON DELETE CASCADE,
  sender_type TEXT NOT NULL CHECK (sender_type IN ('USER', 'AI_BOT')),
  message TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 6. SPRINTS
CREATE TABLE IF NOT EXISTS public.sprints (
  sprint_id BIGSERIAL PRIMARY KEY,
  project_id BIGINT NOT NULL REFERENCES public.projects(project_id) ON DELETE CASCADE,
  sprint_name TEXT NOT NULL,
  start_date DATE,
  end_date DATE,
  status TEXT NOT NULL DEFAULT 'PLANNED' CHECK (status IN ('PLANNED', 'ACTIVE', 'COMPLETED')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 7. TASKS
CREATE TABLE IF NOT EXISTS public.tasks (
  task_id BIGSERIAL PRIMARY KEY,
  sprint_id BIGINT NOT NULL REFERENCES public.sprints(sprint_id) ON DELETE CASCADE,
  assigned_to_user_id BIGINT REFERENCES public.users(user_id) ON DELETE SET NULL,
  title TEXT NOT NULL,
  description TEXT,
  status TEXT NOT NULL DEFAULT 'TODO' CHECK (status IN ('TODO', 'IN_PROGRESS', 'DONE')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 8. PERFORMANCE_LOGS
CREATE TABLE IF NOT EXISTS public.performance_logs (
  performance_log_id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES public.users(user_id) ON DELETE CASCADE,
  task_id BIGINT NOT NULL REFERENCES public.tasks(task_id) ON DELETE CASCADE,
  accuracy_score DOUBLE PRECISION,
  progress_percent DOUBLE PRECISION,
  log_date DATE NOT NULL DEFAULT CURRENT_DATE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Optional: auto-update updated_at (Supabase/Postgres 11+)
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers: Supabase uses Postgres 15; use EXECUTE FUNCTION. (Older Postgres: use EXECUTE PROCEDURE.)
CREATE TRIGGER users_updated_at BEFORE UPDATE ON public.users FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER projects_updated_at BEFORE UPDATE ON public.projects FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER project_assignments_updated_at BEFORE UPDATE ON public.project_assignments FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER backlog_items_updated_at BEFORE UPDATE ON public.backlog_items FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER sprints_updated_at BEFORE UPDATE ON public.sprints FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER tasks_updated_at BEFORE UPDATE ON public.tasks FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER performance_logs_updated_at BEFORE UPDATE ON public.performance_logs FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
