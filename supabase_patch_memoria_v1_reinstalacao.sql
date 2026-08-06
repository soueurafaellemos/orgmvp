begin;

-- Memória é um módulo isolado.
-- Não há relação com products, activation_solutions, venues,
-- suppliers, recommendation_candidates ou recommendation_results.

create table if not exists public.memory_documents (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null
    references public.projects(id)
    on delete cascade,
  title text not null,
  file_name text not null,
  mime_type text not null default 'application/pdf',
  version_label text,
  document_status text not null default 'sent_to_client'
    check (
      document_status in (
        'sent_to_client',
        'revision',
        'approved',
        'executed',
        'internal_reference'
      )
    ),
  page_count integer,
  rendered_pages_count integer not null default 0,
  items_count integer not null default 0,
  visual_crops_count integer not null default 0,
  content_sha256 text not null,
  storage_bucket text,
  storage_path text,
  extraction_status text not null default 'processando'
    check (
      extraction_status in (
        'processando',
        'pronto',
        'erro'
      )
    ),
  strategic_summary text,
  creative_concept text,
  client_brand text,
  event_name text,
  raw_data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint memory_document_project_hash_uidx
    unique (project_id, content_sha256)
);

create index if not exists memory_documents_project_idx
  on public.memory_documents (
    project_id,
    created_at desc
  );

drop trigger if exists memory_documents_set_updated_at
  on public.memory_documents;

create trigger memory_documents_set_updated_at
before update on public.memory_documents
for each row execute function public.set_updated_at();

alter table public.memory_documents enable row level security;
revoke all on public.memory_documents from anon, authenticated;
grant select, insert, update, delete
  on public.memory_documents to service_role, postgres;


create table if not exists public.memory_pages (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null
    references public.projects(id)
    on delete cascade,
  document_id uuid not null
    references public.memory_documents(id)
    on delete cascade,
  page_number integer not null check (page_number > 0),
  slide_title text,
  slide_summary text,
  primary_section text
    check (
      primary_section is null
      or primary_section in (
        'strategy',
        'scenography',
        'activations',
        'gifts',
        'journey_operation',
        'communication',
        'content_agenda',
        'partners_sponsorship',
        'pr_esg_legacy'
      )
    ),
  storage_bucket text not null,
  storage_path text not null,
  content_sha256 text not null,
  raw_data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  constraint memory_page_document_number_uidx
    unique (document_id, page_number)
);

create index if not exists memory_pages_project_idx
  on public.memory_pages (
    project_id,
    document_id,
    page_number
  );

alter table public.memory_pages enable row level security;
revoke all on public.memory_pages from anon, authenticated;
grant select, insert, update, delete
  on public.memory_pages to service_role, postgres;


create table if not exists public.memory_items (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null
    references public.projects(id)
    on delete cascade,
  document_id uuid not null
    references public.memory_documents(id)
    on delete cascade,
  page_id uuid
    references public.memory_pages(id)
    on delete set null,
  source_page integer not null check (source_page > 0),
  section_key text not null
    check (
      section_key in (
        'strategy',
        'scenography',
        'activations',
        'gifts',
        'journey_operation',
        'communication',
        'content_agenda',
        'partners_sponsorship',
        'pr_esg_legacy'
      )
    ),
  item_type text not null default 'Conteúdo',
  title text not null,
  summary text,
  description text,
  item_status text not null default 'Não identificado'
    check (
      item_status in (
        'Referência',
        'Proposto',
        'Opção',
        'Recomendado',
        'Aprovado',
        'Descartado',
        'Executado',
        'Não identificado'
      )
    ),
  tags text[] not null default '{}'::text[],
  objectives text[] not null default '{}'::text[],
  audiences text[] not null default '{}'::text[],
  mechanics text[] not null default '{}'::text[],
  technologies text[] not null default '{}'::text[],
  journey_stage text,
  slide_title text,
  visual_crop jsonb,
  visual_storage_bucket text,
  visual_storage_path text,
  visual_content_sha256 text,
  confidence numeric(5,4),
  evidence text,
  sort_order integer not null default 0,
  raw_data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists memory_items_project_section_idx
  on public.memory_items (
    project_id,
    section_key,
    sort_order,
    source_page
  );

create index if not exists memory_items_document_idx
  on public.memory_items (
    document_id,
    source_page
  );

drop trigger if exists memory_items_set_updated_at
  on public.memory_items;

create trigger memory_items_set_updated_at
before update on public.memory_items
for each row execute function public.set_updated_at();

alter table public.memory_items enable row level security;
revoke all on public.memory_items from anon, authenticated;
grant select, insert, update, delete
  on public.memory_items to service_role, postgres;


create or replace view public.memory_project_overview
with (security_invoker = true)
as
select
  p.id as project_id,
  p.project_name,
  p.client_brand,
  p.event_name,
  p.status,
  count(distinct md.id)::integer
    as memory_documents_count,
  count(distinct mi.id)::integer
    as memory_items_count,
  count(distinct mp.id)::integer
    as memory_pages_count,
  max(
    greatest(
      md.created_at,
      coalesce(mi.updated_at, md.created_at)
    )
  ) as latest_memory_activity
from public.projects p
join public.memory_documents md
  on md.project_id = p.id
left join public.memory_pages mp
  on mp.document_id = md.id
left join public.memory_items mi
  on mi.document_id = md.id
group by
  p.id,
  p.project_name,
  p.client_brand,
  p.event_name,
  p.status;

revoke all on public.memory_project_overview
  from anon, authenticated;

grant select on public.memory_project_overview
  to service_role, postgres;

comment on table public.memory_documents is
  'Apresentações preservadas exclusivamente na Memória de projetos.';

comment on table public.memory_pages is
  'Slides renderizados para consulta contextual dentro da Memória.';

comment on table public.memory_items is
  'Conteúdos estratégicos e visuais vinculados somente ao projeto de origem.';

commit;
