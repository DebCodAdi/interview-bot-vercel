-- MIT Interview Bot: minimal production schema.
-- Run this entire file once in Supabase Dashboard -> SQL Editor -> New query.

create table if not exists public.question_bank (
  id text primary key,
  role text not null,
  question_type text not null check (question_type in ('technical', 'coding')),
  topic text,
  difficulty smallint not null check (difficulty between 1 and 10),
  question text not null,
  key_concepts jsonb not null default '[]'::jsonb,
  follow_up_hints jsonb not null default '[]'::jsonb,
  parameters jsonb not null default '[]'::jsonb,
  examples jsonb not null default '[]'::jsonb,
  test_cases jsonb not null default '[]'::jsonb,
  language_options jsonb not null default '["python", "javascript"]'::jsonb,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists question_bank_lookup_idx
  on public.question_bank (role, question_type, difficulty)
  where is_active = true;

-- Anonymous, short-lived server-side state. This is not a candidate account.
create table if not exists public.interview_sessions (
  session_key uuid primary key,
  role text not null,
  candidate_name text,
  analysis jsonb not null default '{}'::jsonb,
  resume_questions jsonb not null default '[]'::jsonb,
  coding_question jsonb,
  selected_question_ids jsonb not null default '[]'::jsonb,
  call_id text,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null default (now() + interval '24 hours')
);

create index if not exists interview_sessions_expiry_idx
  on public.interview_sessions (expires_at);

create table if not exists public.interview_results (
  id uuid primary key default gen_random_uuid(),
  call_id text unique not null,
  session_key uuid references public.interview_sessions(session_key) on delete set null,
  role text not null,
  transcript jsonb not null default '[]'::jsonb,
  code_result jsonb,
  evaluation jsonb,
  completion_reason text,
  duration_seconds integer,
  created_at timestamptz not null default now()
);

-- The browser must not query private test cases or candidate data directly.
-- Backend calls use the Supabase service-role key, which bypasses RLS.
alter table public.question_bank enable row level security;
alter table public.interview_sessions enable row level security;
alter table public.interview_results enable row level security;
