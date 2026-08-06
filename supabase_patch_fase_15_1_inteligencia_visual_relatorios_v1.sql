begin;

-- ================================================================
-- NAVE by VOE — V27.1
-- FASE 15.1 — INTELIGÊNCIA VISUAL E FECHAMENTO DO PROJETO
-- ================================================================

create table if not exists public.project_report_analyses (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  report_file_id uuid not null references public.project_files(id) on delete cascade,
  report_type text not null default 'post_execution'
    check (report_type in ('post_execution','closure','other')),
  analysis_status text not null default 'processed'
    check (analysis_status in ('processing','processed','review_required','error')),
  event_date date,
  participants_count integer,
  planned_cost numeric,
  actual_cost numeric,
  currency text not null default 'BRL',
  client_satisfaction text,
  executive_summary text,
  objectives_result text,
  commercial_result text,
  execution_result text,
  competitor text,
  loss_reasons text[] not null default '{}'::text[],
  highlights text[] not null default '{}'::text[],
  issues text[] not null default '{}'::text[],
  learnings text[] not null default '{}'::text[],
  recommendations text[] not null default '{}'::text[],
  client_feedback jsonb not null default '[]'::jsonb,
  kpis jsonb not null default '[]'::jsonb,
  activation_results jsonb not null default '[]'::jsonb,
  supplier_evaluations jsonb not null default '[]'::jsonb,
  media_results jsonb not null default '[]'::jsonb,
  item_results jsonb not null default '[]'::jsonb,
  confidence_level text not null default 'incomplete'
    check (confidence_level in ('client_confirmed','voe_confirmed','inferred','incomplete')),
  raw_extraction jsonb not null default '{}'::jsonb,
  processing_error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint project_report_analysis_file_uidx unique (project_id, report_file_id)
);

create index if not exists project_report_analyses_project_idx
  on public.project_report_analyses (project_id, report_type, updated_at desc);

drop trigger if exists project_report_analyses_set_updated_at on public.project_report_analyses;
create trigger project_report_analyses_set_updated_at
before update on public.project_report_analyses
for each row execute function public.set_updated_at();

alter table public.project_report_analyses enable row level security;
revoke all on public.project_report_analyses from anon, authenticated;
grant select, insert, update, delete on public.project_report_analyses to service_role, postgres;

comment on table public.project_report_analyses is
  'Leitura estruturada de relatórios de encerramento e pós-execução.';

commit;
