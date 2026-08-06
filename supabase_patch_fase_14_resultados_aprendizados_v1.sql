begin;

-- ================================================================
-- FASE 14 — RESULTADOS, APRENDIZADOS E ADERÊNCIA AO ORÇAMENTO
--
-- Os dados permanecem vinculados à Memória de cada projeto.
-- Eles não entram na Base de conhecimento e não alteram
-- automaticamente o ranking das recomendações.
-- ================================================================

create table if not exists public.memory_project_outcomes (
  project_id uuid primary key
    references public.projects(id)
    on delete cascade,

  process_type text not null default 'not_informed'
    check (
      process_type in (
        'competition',
        'direct',
        'proactive',
        'renewal',
        'not_informed'
      )
    ),

  commercial_result text not null default 'in_evaluation'
    check (
      commercial_result in (
        'in_evaluation',
        'won',
        'lost',
        'cancelled',
        'suspended',
        'no_return',
        'not_applicable',
        'not_informed'
      )
    ),

  proposal_result text not null default 'not_informed'
    check (
      proposal_result in (
        'fully_approved',
        'partially_approved',
        'not_approved',
        'in_revision',
        'no_feedback',
        'not_informed'
      )
    ),

  execution_result text not null default 'not_informed'
    check (
      execution_result in (
        'executed',
        'partially_executed',
        'not_executed',
        'in_progress',
        'not_applicable',
        'not_informed'
      )
    ),

  result_date date,
  execution_date date,

  contracting_client text,
  partners_involved text,

  result_reasons text[] not null default '{}'::text[],
  result_context text,
  execution_notes text,

  budget_amount numeric,
  currency text not null default 'BRL',

  confidence_level text not null default 'incomplete'
    check (
      confidence_level in (
        'client_confirmed',
        'voe_confirmed',
        'inferred',
        'incomplete'
      )
    ),

  information_source text not null default 'not_informed'
    check (
      information_source in (
        'client_feedback',
        'voe_team',
        'email',
        'meeting',
        'document',
        'other',
        'not_informed'
      )
    ),

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists memory_project_outcomes_set_updated_at
  on public.memory_project_outcomes;

create trigger memory_project_outcomes_set_updated_at
before update on public.memory_project_outcomes
for each row execute function public.set_updated_at();

alter table public.memory_project_outcomes
  enable row level security;

revoke all on public.memory_project_outcomes
  from anon, authenticated;

grant select, insert, update, delete
  on public.memory_project_outcomes
  to service_role, postgres;


create table if not exists public.memory_feedback_entries (
  id uuid primary key default gen_random_uuid(),

  project_id uuid not null
    references public.projects(id)
    on delete cascade,

  feedback_date date,

  source_type text not null default 'not_informed'
    check (
      source_type in (
        'client',
        'procurement',
        'marketing',
        'branding',
        'partner_agency',
        'production',
        'public',
        'internal_team',
        'not_informed'
      )
    ),

  process_stage text not null default 'not_informed'
    check (
      process_stage in (
        'presentation',
        'revision',
        'commercial_decision',
        'production',
        'post_event',
        'not_informed'
      )
    ),

  theme text not null default 'other'
    check (
      theme in (
        'strategy',
        'creative_concept',
        'kv',
        'scenography',
        'activation',
        'gift',
        'journey',
        'operation',
        'technology',
        'budget',
        'timeline',
        'presentation',
        'other'
      )
    ),

  sentiment text not null default 'neutral'
    check (
      sentiment in (
        'positive',
        'negative',
        'neutral',
        'mixed'
      )
    ),

  original_feedback text not null,
  internal_interpretation text,
  action_taken text,

  confidence_level text not null default 'incomplete'
    check (
      confidence_level in (
        'client_confirmed',
        'voe_confirmed',
        'inferred',
        'incomplete'
      )
    ),

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists memory_feedback_project_idx
  on public.memory_feedback_entries (
    project_id,
    feedback_date desc,
    created_at desc
  );

drop trigger if exists memory_feedback_entries_set_updated_at
  on public.memory_feedback_entries;

create trigger memory_feedback_entries_set_updated_at
before update on public.memory_feedback_entries
for each row execute function public.set_updated_at();

alter table public.memory_feedback_entries
  enable row level security;

revoke all on public.memory_feedback_entries
  from anon, authenticated;

grant select, insert, update, delete
  on public.memory_feedback_entries
  to service_role, postgres;


create table if not exists public.memory_item_outcomes (
  item_id uuid primary key
    references public.memory_items(id)
    on delete cascade,

  project_id uuid not null
    references public.projects(id)
    on delete cascade,

  outcome_status text not null default 'unassessed'
    check (
      outcome_status in (
        'unassessed',
        'approved',
        'approved_with_changes',
        'not_approved',
        'replaced',
        'removed_budget',
        'removed_timeline',
        'executed',
        'not_executed',
        'unknown'
      )
    ),

  decision_reason text,
  feedback_summary text,
  execution_notes text,

  confidence_level text not null default 'incomplete'
    check (
      confidence_level in (
        'client_confirmed',
        'voe_confirmed',
        'inferred',
        'incomplete'
      )
    ),

  information_source text not null default 'not_informed'
    check (
      information_source in (
        'client_feedback',
        'voe_team',
        'email',
        'meeting',
        'document',
        'other',
        'not_informed'
      )
    ),

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists memory_item_outcomes_project_idx
  on public.memory_item_outcomes (
    project_id,
    outcome_status
  );

drop trigger if exists memory_item_outcomes_set_updated_at
  on public.memory_item_outcomes;

create trigger memory_item_outcomes_set_updated_at
before update on public.memory_item_outcomes
for each row execute function public.set_updated_at();

alter table public.memory_item_outcomes
  enable row level security;

revoke all on public.memory_item_outcomes
  from anon, authenticated;

grant select, insert, update, delete
  on public.memory_item_outcomes
  to service_role, postgres;


create table if not exists public.memory_cost_documents (
  id uuid primary key default gen_random_uuid(),

  project_id uuid not null
    references public.projects(id)
    on delete cascade,

  title text not null,
  file_name text not null,
  mime_type text not null,
  sheet_name text,
  header_row integer,

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

  total_items integer not null default 0,
  included_items integer not null default 0,
  optional_items integer not null default 0,
  pending_items integer not null default 0,

  total_base numeric,
  fees_total numeric,
  charges_total numeric,
  client_total numeric,
  currency text not null default 'BRL',

  macros_present boolean not null default false,

  metadata jsonb not null default '{}'::jsonb,
  diagnostic jsonb not null default '{}'::jsonb,
  raw_data jsonb not null default '{}'::jsonb,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint memory_cost_document_project_hash_uidx
    unique (project_id, content_sha256)
);

create index if not exists memory_cost_documents_project_idx
  on public.memory_cost_documents (
    project_id,
    created_at desc
  );

drop trigger if exists memory_cost_documents_set_updated_at
  on public.memory_cost_documents;

create trigger memory_cost_documents_set_updated_at
before update on public.memory_cost_documents
for each row execute function public.set_updated_at();

alter table public.memory_cost_documents
  enable row level security;

revoke all on public.memory_cost_documents
  from anon, authenticated;

grant select, insert, update, delete
  on public.memory_cost_documents
  to service_role, postgres;


create table if not exists public.memory_cost_items (
  id uuid primary key default gen_random_uuid(),

  project_id uuid not null
    references public.projects(id)
    on delete cascade,

  cost_document_id uuid not null
    references public.memory_cost_documents(id)
    on delete cascade,

  source_sheet text not null,
  source_row integer not null,

  item_code text,
  category text,
  item_name text not null,
  description text,
  billing_type text,

  quantity numeric,
  period numeric,
  unit_value numeric,
  base_value numeric,
  fees_value numeric,
  charges_value numeric,
  client_total numeric,

  item_status text not null default 'included'
    check (
      item_status in (
        'included',
        'optional',
        'client_responsibility',
        'pending',
        'reserve',
        'no_value'
      )
    ),

  estimate_type text not null default 'quoted'
    check (
      estimate_type in (
        'quoted',
        'estimated',
        'reserve',
        'waiting_supplier',
        'no_value'
      )
    ),

  flags text[] not null default '{}'::text[],
  raw_data jsonb not null default '{}'::jsonb,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint memory_cost_item_source_uidx
    unique (
      cost_document_id,
      source_sheet,
      source_row
    )
);

create index if not exists memory_cost_items_project_idx
  on public.memory_cost_items (
    project_id,
    category,
    source_row
  );

drop trigger if exists memory_cost_items_set_updated_at
  on public.memory_cost_items;

create trigger memory_cost_items_set_updated_at
before update on public.memory_cost_items
for each row execute function public.set_updated_at();

alter table public.memory_cost_items
  enable row level security;

revoke all on public.memory_cost_items
  from anon, authenticated;

grant select, insert, update, delete
  on public.memory_cost_items
  to service_role, postgres;


create table if not exists public.memory_cost_links (
  id uuid primary key default gen_random_uuid(),

  project_id uuid not null
    references public.projects(id)
    on delete cascade,

  cost_item_id uuid not null
    references public.memory_cost_items(id)
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

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint memory_cost_link_pair_uidx
    unique (
      cost_item_id,
      memory_item_id
    )
);

create index if not exists memory_cost_links_project_idx
  on public.memory_cost_links (
    project_id,
    link_status,
    match_score desc
  );

create index if not exists memory_cost_links_memory_item_idx
  on public.memory_cost_links (
    memory_item_id,
    link_status
  );

drop trigger if exists memory_cost_links_set_updated_at
  on public.memory_cost_links;

create trigger memory_cost_links_set_updated_at
before update on public.memory_cost_links
for each row execute function public.set_updated_at();

alter table public.memory_cost_links
  enable row level security;

revoke all on public.memory_cost_links
  from anon, authenticated;

grant select, insert, update, delete
  on public.memory_cost_links
  to service_role, postgres;


create or replace view public.memory_learning_overview
with (security_invoker = true)
as
select
  p.id as project_id,

  mpo.process_type,
  mpo.commercial_result,
  mpo.proposal_result,
  mpo.execution_result,
  mpo.budget_amount,
  mpo.currency,

  count(distinct mfe.id)::integer
    as feedback_count,

  count(distinct mio.item_id)::integer
    as evaluated_items_count,

  count(distinct mcd.id)::integer
    as cost_documents_count,

  coalesce(
    max(mcd.client_total),
    0
  ) as latest_proposal_total

from public.projects p

left join public.memory_project_outcomes mpo
  on mpo.project_id = p.id

left join public.memory_feedback_entries mfe
  on mfe.project_id = p.id

left join public.memory_item_outcomes mio
  on mio.project_id = p.id

left join public.memory_cost_documents mcd
  on mcd.project_id = p.id

group by
  p.id,
  mpo.process_type,
  mpo.commercial_result,
  mpo.proposal_result,
  mpo.execution_result,
  mpo.budget_amount,
  mpo.currency;

revoke all on public.memory_learning_overview
  from anon, authenticated;

grant select on public.memory_learning_overview
  to service_role, postgres;

comment on table public.memory_project_outcomes is
  'Resultado comercial, aprovação, execução e budget do projeto.';

comment on table public.memory_feedback_entries is
  'Feedbacks históricos recebidos sobre o projeto.';

comment on table public.memory_item_outcomes is
  'Resultado e decisão no nível das fichas da Memória.';

comment on table public.memory_cost_documents is
  'Planilhas de custos vinculadas ao projeto para análise histórica.';

comment on table public.memory_cost_items is
  'Itens estruturados das planilhas de custos.';

comment on table public.memory_cost_links is
  'Correlação revisável entre linhas de custo e fichas da Memória.';

commit;
