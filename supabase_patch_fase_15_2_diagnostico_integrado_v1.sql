begin;

-- ================================================================
-- NAVE by VOE — V27.2 / FASE 15.2
-- DIAGNÓSTICO INTEGRADO E MATRIZ DE EXECUÇÃO
--
-- Preserva snapshots cumulativos do cruzamento entre:
-- briefing, apresentação, planilha, feedbacks e pós-evento.
-- ================================================================

create table if not exists public.project_intelligence_snapshots (
  id uuid primary key default gen_random_uuid(),

  project_id uuid not null
    references public.projects(id)
    on delete cascade,

  source_signature text not null,

  coverage jsonb not null default '{}'::jsonb,
  metrics jsonb not null default '{}'::jsonb,
  matrix jsonb not null default '[]'::jsonb,
  findings jsonb not null default '[]'::jsonb,
  recommendations jsonb not null default '[]'::jsonb,
  discrepancies jsonb not null default '{}'::jsonb,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint project_intelligence_snapshot_source_uidx
    unique (project_id, source_signature)
);

create index if not exists project_intelligence_snapshots_project_idx
  on public.project_intelligence_snapshots (
    project_id,
    created_at desc
  );

drop trigger if exists project_intelligence_snapshots_set_updated_at
  on public.project_intelligence_snapshots;

create trigger project_intelligence_snapshots_set_updated_at
before update on public.project_intelligence_snapshots
for each row execute function public.set_updated_at();

alter table public.project_intelligence_snapshots
  enable row level security;

revoke all on public.project_intelligence_snapshots
  from anon, authenticated;

grant select, insert, update, delete
  on public.project_intelligence_snapshots
  to service_role, postgres;

comment on table public.project_intelligence_snapshots is
  'Snapshots cumulativos do diagnóstico briefing × proposta × custo × execução × resultado.';

commit;
