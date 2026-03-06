-- Run this in Supabase SQL Editor to create the session records table.
-- Dashboard: Your project → SQL Editor → New query → paste and run.

create table if not exists public.session_records (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz default now(),
  tutor_name text,
  tutor_email text,
  student_name text,
  session_date text,
  session_number text,
  course_type text,
  score int,
  rating text,
  report_text text,
  transcript_text text,
  host_data jsonb,
  fathom_notes text
);

-- Optional: enable RLS and add policy if you want to restrict access.
-- For server-side only access with service key, you can leave RLS off.
-- alter table public.session_records enable row level security;
-- create policy "Service role only" on public.session_records for all using (true);
