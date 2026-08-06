begin;

-- ================================================================
-- NAVE by VOE — FASE 15
-- WORKSPACE UNIFICADO DO PROJETO
--
-- Cria uma central genérica e versionada de arquivos do projeto.
-- Briefings estruturados, apresentações analisadas, custos, feedbacks
-- e resultados já existentes continuam preservados em suas tabelas.
-- ================================================================

create table if not exists public.project_files (
  id uuid primary key default gen_random_uuid(),

  project_id uuid not null
    references public.projects(id)
    on delete cascade,

  file_role text not null
    check (
      file_role in (
        'briefing_original',
        'cost_sheet',
        'final_presentation',
        'feedback',
        'approval',
        'closure_report',
        'post_execution_report',
        'production_file',
        'supplier_reference',
        'gift_presskit_reference',
        'project_document',
        'other'
      )
    ),

  title text not null,
  file_name text not null,
  mime_type text,
  file_size_bytes bigint,
  content_sha256 text not null,

  version_number integer not null default 1
    check (version_number > 0),

  storage_bucket text not null default 'nave-project-files',
  storage_path text not null,

  notes text,
  metadata jsonb not null default '{}'::jsonb,

  is_current boolean not null default true,
  is_archived boolean not null default false,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint project_files_project_role_hash_uidx
    unique (
      project_id,
      file_role,
      content_sha256
    )
);

create index if not exists project_files_project_idx
  on public.project_files (
    project_id,
    file_role,
    is_current,
    created_at desc
  );

create index if not exists project_files_role_idx
  on public.project_files (
    file_role,
    created_at desc
  );

drop trigger if exists project_files_set_updated_at
  on public.project_files;

create trigger project_files_set_updated_at
before update on public.project_files
for each row execute function public.set_updated_at();

alter table public.project_files
  enable row level security;

revoke all on public.project_files
  from anon, authenticated;

grant select, insert, update, delete
  on public.project_files
  to service_role, postgres;


-- Próxima ação e observações operacionais ficam no raw_data do projeto,
-- preservando compatibilidade com a estrutura atual.
comment on table public.project_files is
  'Central versionada de arquivos do workspace unificado de cada projeto.';

commit;
