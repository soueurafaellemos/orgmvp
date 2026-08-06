begin;

-- ================================================================
-- FASE 14.1 — BRIEFING & ADERÊNCIA
--
-- O briefing permanece vinculado ao projeto da Memória.
-- Não alimenta diretamente a Base de conhecimento e não altera
-- automaticamente o ranking das recomendações.
-- ================================================================

create table if not exists public.memory_briefing_documents (
  id uuid primary key default gen_random_uuid(),

  project_id uuid not null
    references public.projects(id)
    on delete cascade,

  title text not null,
  file_name text not null,
  mime_type text not null,
  content_sha256 text not null,

  storage_bucket text,
  storage_path text,

  extraction_status text not null default 'pronto'
    check (
      extraction_status in (
        'processando',
        'pronto',
        'erro'
      )
    ),

  requirements_count integer not null default 0,

  budget_amount numeric,
  currency text not null default 'BRL',

  objective text,
  audience text,

  metadata jsonb not null default '{}'::jsonb,
  diagnostic jsonb not null default '{}'::jsonb,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint memory_briefing_project_hash_uidx
    unique (
      project_id,
      content_sha256
    )
);

create index if not exists memory_briefing_documents_project_idx
  on public.memory_briefing_documents (
    project_id,
    created_at desc
  );

drop trigger if exists memory_briefing_documents_set_updated_at
  on public.memory_briefing_documents;

create trigger memory_briefing_documents_set_updated_at
before update on public.memory_briefing_documents
for each row execute function public.set_updated_at();

alter table public.memory_briefing_documents
  enable row level security;

revoke all on public.memory_briefing_documents
  from anon, authenticated;

grant select, insert, update, delete
  on public.memory_briefing_documents
  to service_role, postgres;


create table if not exists public.memory_briefing_requirements (
  id uuid primary key default gen_random_uuid(),

  project_id uuid not null
    references public.projects(id)
    on delete cascade,

  briefing_document_id uuid not null
    references public.memory_briefing_documents(id)
    on delete cascade,

  requirement_type text not null
    check (
      requirement_type in (
        'objective',
        'deliverable',
        'mandatory',
        'restriction',
        'audience',
        'logistics',
        'budget',
        'kpi',
        'operation',
        'communication',
        'desirable',
        'context'
      )
    ),

  title text not null,
  description text,

  priority text not null default 'not_informed'
    check (
      priority in (
        'critical',
        'high',
        'medium',
        'low',
        'not_informed'
      )
    ),

  mandatory boolean not null default false,

  source_reference text,
  source_quote text,

  tags text[] not null default '{}'::text[],
  sort_order integer not null default 0,

  adherence_status text not null default 'not_assessed'
    check (
      adherence_status in (
        'not_assessed',
        'fulfilled',
        'partially_fulfilled',
        'not_fulfilled',
        'exceeded',
        'changed_justified',
        'removed_budget',
        'removed_timeline',
        'not_applicable',
        'unproven'
      )
    ),

  adherence_evidence text,
  adherence_notes text,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists memory_briefing_requirements_project_idx
  on public.memory_briefing_requirements (
    project_id,
    requirement_type,
    sort_order
  );

drop trigger if exists memory_briefing_requirements_set_updated_at
  on public.memory_briefing_requirements;

create trigger memory_briefing_requirements_set_updated_at
before update on public.memory_briefing_requirements
for each row execute function public.set_updated_at();

alter table public.memory_briefing_requirements
  enable row level security;

revoke all on public.memory_briefing_requirements
  from anon, authenticated;

grant select, insert, update, delete
  on public.memory_briefing_requirements
  to service_role, postgres;


create table if not exists public.memory_briefing_links (
  id uuid primary key default gen_random_uuid(),

  project_id uuid not null
    references public.projects(id)
    on delete cascade,

  requirement_id uuid not null
    references public.memory_briefing_requirements(id)
    on delete cascade,

  memory_item_id uuid not null
    references public.memory_items(id)
    on delete cascade,

  match_score numeric(5,4),
  match_reason text,

  link_status text not null default 'suggested'
    check (
      link_status in (
        'suggested',
        'confirmed',
        'rejected'
      )
    ),

  adherence_status text not null default 'not_assessed'
    check (
      adherence_status in (
        'not_assessed',
        'fulfilled',
        'partially_fulfilled',
        'not_fulfilled',
        'exceeded',
        'changed_justified',
        'removed_budget',
        'removed_timeline',
        'not_applicable',
        'unproven'
      )
    ),

  evidence text,
  notes text,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint memory_briefing_link_pair_uidx
    unique (
      requirement_id,
      memory_item_id
    )
);

create index if not exists memory_briefing_links_project_idx
  on public.memory_briefing_links (
    project_id,
    adherence_status,
    match_score desc
  );

create index if not exists memory_briefing_links_item_idx
  on public.memory_briefing_links (
    memory_item_id,
    link_status
  );

drop trigger if exists memory_briefing_links_set_updated_at
  on public.memory_briefing_links;

create trigger memory_briefing_links_set_updated_at
before update on public.memory_briefing_links
for each row execute function public.set_updated_at();

alter table public.memory_briefing_links
  enable row level security;

revoke all on public.memory_briefing_links
  from anon, authenticated;

grant select, insert, update, delete
  on public.memory_briefing_links
  to service_role, postgres;


create or replace view public.memory_briefing_adherence_overview
with (security_invoker = true)
as
select
  p.id as project_id,

  count(distinct mbd.id)::integer
    as briefing_documents_count,

  count(distinct mbr.id)::integer
    as requirements_count,

  count(
    distinct mbr.id
  ) filter (
    where mbr.mandatory = true
  )::integer as mandatory_requirements_count,

  count(
    distinct mbl.requirement_id
  )::integer as linked_requirements_count,

  count(
    distinct mbl.requirement_id
  ) filter (
    where mbl.adherence_status = 'fulfilled'
  )::integer as fulfilled_requirements_count,

  count(
    distinct mbl.requirement_id
  ) filter (
    where mbl.adherence_status = 'partially_fulfilled'
  )::integer as partially_fulfilled_requirements_count,

  count(
    distinct mbl.requirement_id
  ) filter (
    where mbl.adherence_status = 'not_fulfilled'
  )::integer as not_fulfilled_requirements_count,

  max(mbd.budget_amount)
    as briefing_budget_amount,

  max(mbd.currency)
    as currency

from public.projects p

left join public.memory_briefing_documents mbd
  on mbd.project_id = p.id

left join public.memory_briefing_requirements mbr
  on mbr.project_id = p.id

left join public.memory_briefing_links mbl
  on mbl.project_id = p.id

group by p.id;

revoke all on public.memory_briefing_adherence_overview
  from anon, authenticated;

grant select on public.memory_briefing_adherence_overview
  to service_role, postgres;


comment on table public.memory_briefing_documents is
  'Briefings iniciais vinculados ao projeto da Memória.';

comment on table public.memory_briefing_requirements is
  'Demandas, obrigatoriedades, restrições e entregáveis do briefing.';

comment on table public.memory_briefing_links is
  'Correlação revisável entre briefing e fichas da apresentação.';

commit;
