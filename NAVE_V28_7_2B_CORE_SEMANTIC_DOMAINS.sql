-- NAVE by VOE · V28.7.2B
-- Core Semantic Domains — Strategy, Creative Platform & Experience Architecture
-- Shadow rollout. Does NOT modify V28.7.1D Truth Gate and does NOT rebuild Graph V28.6.

begin;

create extension if not exists pgcrypto with schema extensions;

-- --------------------------------------------------------------------------
-- 0. Prerequisites — fail closed.
-- --------------------------------------------------------------------------
do $$
begin
  if to_regclass('public.projects') is null
     or to_regclass('public.project_domain_migration_state') is null then
    raise exception 'V28.7.2B prerequisite missing: Project Domain Foundation';
  end if;
  if to_regclass('public.semantic_observations') is null
     or to_regclass('public.project_context_elements') is null
     or to_regclass('public.project_solution_instances') is null
     or to_regclass('public.project_solution_occurrences') is null then
    raise exception 'V28.7.2B prerequisite missing: V28.7.2A Reconciliation Kernel';
  end if;
  if to_regclass('public.source_assets') is null
     or to_regclass('public.evidence_units') is null
     or to_regclass('public.knowledge_entities') is null
     or to_regclass('public.knowledge_relations') is null
     or to_regclass('public.relation_evidence') is null then
    raise exception 'V28.7.2B prerequisite missing: Intelligence Foundation';
  end if;
  if to_regclass('public.domain_object_evidence') is null
     or to_regclass('public.domain_object_governance') is null then
    raise exception 'V28.7.2B prerequisite missing: Domain provenance/governance';
  end if;
  if to_regclass('public.entity_outcome_truth_status') is null
     or to_regclass('public.entity_current_outcomes') is null then
    raise exception 'V28.7.2B prerequisite missing: V28.7.1D Truth Gate';
  end if;
end $$;

-- --------------------------------------------------------------------------
-- 1. Ontology — new semantic domain mirrors.
-- --------------------------------------------------------------------------
insert into public.ontology_entity_types(
  code, label_pt, label_en, parent_code,
  is_global_canonical, is_project_instance_allowed,
  description, active, schema_version
)
values
  ('strategy_element','Elemento estratégico','Strategy element',null,false,true,'Elemento evidence-backed do Strategy Domain; nunca Project Solution.',true,1),
  ('creative_platform','Plataforma criativa','Creative platform',null,false,true,'Sistema/conceito criativo que expressa a estratégia.',true,1),
  ('creative_element','Elemento criativo','Creative element','creative_platform',false,true,'POV, big idea, narrativa, mensagem, código ou regra pertencente a uma plataforma criativa.',true,1),
  ('experience_architecture','Arquitetura da experiência','Experience architecture',null,false,true,'Orquestração evidence-backed da experiência/jornada.',true,1),
  ('journey_moment','Momento da jornada','Journey moment','experience_architecture',false,true,'Stage/momento/touchpoint de uma arquitetura de experiência.',true,1)
on conflict (code) do update set
  label_pt = excluded.label_pt,
  label_en = excluded.label_en,
  parent_code = excluded.parent_code,
  is_global_canonical = excluded.is_global_canonical,
  is_project_instance_allowed = excluded.is_project_instance_allowed,
  description = excluded.description,
  active = true,
  updated_at = now();

insert into public.ontology_relation_types as ort(
  code, label_pt, label_en, source_types, target_types, inverse_code,
  is_symmetric, is_temporal, allows_multiple, relation_family,
  description, active, schema_version
)
values
  ('informs','Informa','Informs',array['context_element','requirement'],array['strategy_element'],null,false,true,true,'semantic','Contexto/requisito informa estratégia quando há provenance suficiente.',true,1),
  ('supports','Sustenta','Supports',array['strategy_element'],array['strategy_element'],null,false,true,true,'semantic','Um elemento estratégico sustenta outro.',true,1),
  ('contradicts','Contradiz','Contradicts',array['strategy_element'],array['strategy_element'],null,true,true,true,'semantic','Contradição explícita entre elementos estratégicos.',true,1),
  ('expressed_by','Expresso por','Expressed by',array['strategy_element'],array['creative_platform'],null,false,true,true,'semantic','A estratégia encontra expressão numa plataforma criativa.',true,1),
  ('orchestrated_as','Orquestrado como','Orchestrated as',array['creative_platform'],array['experience_architecture'],null,false,true,true,'semantic','A plataforma criativa é organizada como arquitetura de experiência.',true,1),
  ('governs','Governa','Governs',array['strategy_element','creative_platform'],array['journey_moment','solution','activation'],null,false,true,true,'semantic','Princípio/plataforma governa um momento ou solução quando comprovado.',true,1),
  ('contains','Contém','Contains',array['creative_platform','experience_architecture','journey_moment'],array['creative_element','journey_moment','solution','activation'],null,false,true,true,'structure','Relação estrutural de composição/containment evidence-backed.',true,1)
on conflict (code) do update set
  -- Preserve pre-existing ontology semantics; B only broadens allowed endpoint types.
  source_types = array(
    select distinct u.x from unnest(coalesce(ort.source_types,'{}'::text[]) || excluded.source_types) as u(x)
  ),
  target_types = array(
    select distinct u.x from unnest(coalesce(ort.target_types,'{}'::text[]) || excluded.target_types) as u(x)
  ),
  active = true,
  schema_version = greatest(ort.schema_version, excluded.schema_version),
  updated_at = now();

-- --------------------------------------------------------------------------
-- 2. Extend Semantic Observations — one staging table across domains.
-- --------------------------------------------------------------------------
alter table public.semantic_observations
  add column if not exists domain_hint text,
  add column if not exists semantic_role text,
  add column if not exists assertion_mode text;

alter table public.semantic_observations
  drop constraint if exists semantic_observations_observation_kind_check;
alter table public.semantic_observations
  add constraint semantic_observations_observation_kind_check
  check (observation_kind in (
    'solution_candidate','solution_mention','material_mention',
    'context_signal','requirement_signal',
    'strategy_signal','creative_signal','experience_signal','journey_signal','relation_signal',
    'other'
  ));

alter table public.semantic_observations
  drop constraint if exists semantic_observations_domain_hint_check;
alter table public.semantic_observations
  add constraint semantic_observations_domain_hint_check
  check (domain_hint is null or domain_hint in (
    'context','requirement','strategy','creative','experience','journey',
    'solution','material','relation','other'
  ));

alter table public.semantic_observations
  drop constraint if exists semantic_observations_assertion_mode_check;
alter table public.semantic_observations
  add constraint semantic_observations_assertion_mode_check
  check (assertion_mode is null or assertion_mode in (
    'source_explicit','evidence_synthesis','human_confirmed','analyst_inference','unknown'
  ));

alter table public.semantic_observations
  drop constraint if exists semantic_observations_resolution_action_check;
alter table public.semantic_observations
  add constraint semantic_observations_resolution_action_check
  check (resolution_action in (
    'none','attach_occurrence','create_instance','review_required',
    'no_domain_object','insufficient_evidence','reconcile_domain_object'
  ));

create index if not exists semantic_observations_domain_idx
  on public.semantic_observations(project_id, domain_hint, semantic_role, status, updated_at desc)
  where domain_hint is not null;

-- --------------------------------------------------------------------------
-- 3. Strategy Domain.
-- --------------------------------------------------------------------------
create table if not exists public.project_strategy_elements (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  entity_id uuid not null unique references public.knowledge_entities(id) on delete restrict,
  strategy_key text not null,
  strategy_type text not null check (strategy_type in (
    'challenge','tension','insight','opportunity','territory','strategic_direction',
    'pillar','brand_role','audience_role','experience_role','strategic_principle',
    'materialization_criterion'
  )),
  title text not null,
  statement text not null,
  assertion_mode text not null check (assertion_mode in ('source_explicit','evidence_synthesis','human_confirmed')),
  scope jsonb not null default '{}'::jsonb,
  attributes jsonb not null default '{}'::jsonb,
  source_observation_id uuid references public.semantic_observations(id) on delete set null,
  source_evidence_id uuid not null references public.evidence_units(id) on delete restrict,
  confidence numeric(5,4) check (confidence is null or confidence between 0 and 1),
  authority_score numeric(5,4) check (authority_score is null or authority_score between 0 and 1),
  lifecycle_status text not null default 'active' check (lifecycle_status in ('active','superseded','invalidated','review_required')),
  normalization_run_id uuid references public.intelligence_runs(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint project_strategy_elements_key_uidx unique(project_id, strategy_key)
);
create index if not exists project_strategy_elements_project_idx
  on public.project_strategy_elements(project_id, strategy_type, lifecycle_status, updated_at desc);

-- --------------------------------------------------------------------------
-- 4. Creative Platform / Concept System.
-- --------------------------------------------------------------------------
create table if not exists public.project_creative_platforms (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  entity_id uuid not null unique references public.knowledge_entities(id) on delete restrict,
  platform_key text not null,
  name text not null,
  description text,
  assertion_mode text not null check (assertion_mode in ('source_explicit','evidence_synthesis','human_confirmed')),
  attributes jsonb not null default '{}'::jsonb,
  source_observation_id uuid references public.semantic_observations(id) on delete set null,
  source_evidence_id uuid not null references public.evidence_units(id) on delete restrict,
  confidence numeric(5,4) check (confidence is null or confidence between 0 and 1),
  authority_score numeric(5,4) check (authority_score is null or authority_score between 0 and 1),
  lifecycle_status text not null default 'active' check (lifecycle_status in ('active','superseded','invalidated','review_required')),
  normalization_run_id uuid references public.intelligence_runs(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint project_creative_platforms_key_uidx unique(project_id, platform_key)
);
create index if not exists project_creative_platforms_project_idx
  on public.project_creative_platforms(project_id, lifecycle_status, updated_at desc);

create table if not exists public.project_creative_elements (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  platform_id uuid not null references public.project_creative_platforms(id) on delete cascade,
  entity_id uuid not null unique references public.knowledge_entities(id) on delete restrict,
  element_key text not null,
  creative_type text not null check (creative_type in (
    'big_idea','proposition','pov','naming','narrative','creative_territory','message',
    'message_hierarchy','visual_system','proprietary_code','materialization_rule'
  )),
  title text not null,
  statement text not null,
  assertion_mode text not null check (assertion_mode in ('source_explicit','evidence_synthesis','human_confirmed')),
  attributes jsonb not null default '{}'::jsonb,
  source_observation_id uuid references public.semantic_observations(id) on delete set null,
  source_evidence_id uuid not null references public.evidence_units(id) on delete restrict,
  confidence numeric(5,4) check (confidence is null or confidence between 0 and 1),
  authority_score numeric(5,4) check (authority_score is null or authority_score between 0 and 1),
  lifecycle_status text not null default 'active' check (lifecycle_status in ('active','superseded','invalidated','review_required')),
  normalization_run_id uuid references public.intelligence_runs(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint project_creative_elements_key_uidx unique(project_id, element_key)
);
create index if not exists project_creative_elements_project_idx
  on public.project_creative_elements(project_id, creative_type, lifecycle_status, updated_at desc);
create index if not exists project_creative_elements_platform_idx
  on public.project_creative_elements(platform_id, lifecycle_status);

-- --------------------------------------------------------------------------
-- 5. Experience Architecture / Journey.
-- --------------------------------------------------------------------------
create table if not exists public.project_experience_architectures (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  entity_id uuid not null unique references public.knowledge_entities(id) on delete restrict,
  architecture_key text not null,
  name text not null,
  experience_principle text,
  participation_logic text,
  flow_summary text,
  assertion_mode text not null check (assertion_mode in ('source_explicit','evidence_synthesis','human_confirmed')),
  attributes jsonb not null default '{}'::jsonb,
  source_observation_id uuid references public.semantic_observations(id) on delete set null,
  source_evidence_id uuid not null references public.evidence_units(id) on delete restrict,
  confidence numeric(5,4) check (confidence is null or confidence between 0 and 1),
  authority_score numeric(5,4) check (authority_score is null or authority_score between 0 and 1),
  lifecycle_status text not null default 'active' check (lifecycle_status in ('active','superseded','invalidated','review_required')),
  normalization_run_id uuid references public.intelligence_runs(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint project_experience_architectures_key_uidx unique(project_id, architecture_key)
);
create index if not exists project_experience_architectures_project_idx
  on public.project_experience_architectures(project_id, lifecycle_status, updated_at desc);

create table if not exists public.project_journey_moments (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  architecture_id uuid not null references public.project_experience_architectures(id) on delete cascade,
  entity_id uuid not null unique references public.knowledge_entities(id) on delete restrict,
  moment_key text not null,
  sequence_index integer,
  moment_type text not null,
  title text not null,
  purpose text,
  participant_action text,
  experience_role text,
  assertion_mode text not null check (assertion_mode in ('source_explicit','evidence_synthesis','human_confirmed')),
  architecture_association_mode text not null default 'source_explicit'
    check (architecture_association_mode in ('source_explicit','evidence_synthesis','human_confirmed')),
  attributes jsonb not null default '{}'::jsonb,
  source_observation_id uuid references public.semantic_observations(id) on delete set null,
  source_evidence_id uuid not null references public.evidence_units(id) on delete restrict,
  confidence numeric(5,4) check (confidence is null or confidence between 0 and 1),
  authority_score numeric(5,4) check (authority_score is null or authority_score between 0 and 1),
  lifecycle_status text not null default 'active' check (lifecycle_status in ('active','superseded','invalidated','review_required')),
  normalization_run_id uuid references public.intelligence_runs(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint project_journey_moments_key_uidx unique(project_id, moment_key)
);
create index if not exists project_journey_moments_project_idx
  on public.project_journey_moments(project_id, moment_type, lifecycle_status, sequence_index);
create index if not exists project_journey_moments_architecture_idx
  on public.project_journey_moments(architecture_id, lifecycle_status, sequence_index);

-- --------------------------------------------------------------------------
-- 6. Semantic truth status — Domain Truth is not Analyst synthesis.
-- --------------------------------------------------------------------------
create or replace view public.project_core_semantic_truth_status
with (security_invoker = true)
as
with latest_review as (
  select distinct on (ir.object_id)
    ir.object_id,
    ir.decision,
    ir.created_at
  from public.intelligence_reviews ir
  where ir.object_type = 'semantic_observation'
  order by ir.object_id, ir.created_at desc
), domain_rows as (
  select project_id, 'project_strategy_elements'::text as domain_table, id as domain_id, entity_id,
         strategy_type as semantic_type, assertion_mode, source_observation_id, source_evidence_id,
         lifecycle_status, normalization_run_id
  from public.project_strategy_elements
  union all
  select project_id, 'project_creative_platforms', id, entity_id,
         'creative_platform', assertion_mode, source_observation_id, source_evidence_id,
         lifecycle_status, normalization_run_id
  from public.project_creative_platforms
  union all
  select project_id, 'project_creative_elements', id, entity_id,
         creative_type, assertion_mode, source_observation_id, source_evidence_id,
         lifecycle_status, normalization_run_id
  from public.project_creative_elements
  union all
  select project_id, 'project_experience_architectures', id, entity_id,
         'experience_architecture', assertion_mode, source_observation_id, source_evidence_id,
         lifecycle_status, normalization_run_id
  from public.project_experience_architectures
  union all
  select project_id, 'project_journey_moments', id, entity_id,
         moment_type, assertion_mode, source_observation_id, source_evidence_id,
         lifecycle_status, normalization_run_id
  from public.project_journey_moments
)
select
  d.*,
  exists (
    select 1
    from public.domain_object_evidence doe
    join public.evidence_units eu on eu.id=doe.evidence_unit_id and eu.is_current=true
    where doe.object_entity_id=d.entity_id
  ) as has_current_evidence,
  lr.decision as latest_human_review,
  case
    when d.lifecycle_status <> 'active' then 'unsupported'
    when lr.decision = 'reject' then 'unsupported'
    when lr.decision in ('needs_evidence','correct','merge','split') then 'review_required'
    when d.assertion_mode = 'human_confirmed' and lr.decision = 'confirm' then 'human_confirmed'
    when d.assertion_mode = 'source_explicit' and exists (
      select 1 from public.domain_object_evidence doe
      join public.evidence_units eu on eu.id=doe.evidence_unit_id and eu.is_current=true
      where doe.object_entity_id=d.entity_id
    ) then 'verified_explicit'
    when d.assertion_mode = 'evidence_synthesis' and exists (
      select 1 from public.domain_object_evidence doe
      join public.evidence_units eu on eu.id=doe.evidence_unit_id and eu.is_current=true
      where doe.object_entity_id=d.entity_id
    ) then 'verified_synthesis'
    else 'unsupported'
  end as truth_state
from domain_rows d
left join latest_review lr on lr.object_id = d.source_observation_id;

create or replace view public.project_core_semantic_status
with (security_invoker = true)
as
select
  p.id as project_id,
  (select count(*)::integer from public.project_strategy_elements x where x.project_id=p.id and x.lifecycle_status='active') as strategy_elements,
  (select count(*)::integer from public.project_creative_platforms x where x.project_id=p.id and x.lifecycle_status='active') as creative_platforms,
  (select count(*)::integer from public.project_creative_elements x where x.project_id=p.id and x.lifecycle_status='active') as creative_elements,
  (select count(*)::integer from public.project_experience_architectures x where x.project_id=p.id and x.lifecycle_status='active') as experience_architectures,
  (select count(*)::integer from public.project_journey_moments x where x.project_id=p.id and x.lifecycle_status='active') as journey_moments,
  (select count(*)::integer from public.project_core_semantic_truth_status t where t.project_id=p.id and t.truth_state='verified_explicit') as verified_explicit,
  (select count(*)::integer from public.project_core_semantic_truth_status t where t.project_id=p.id and t.truth_state='verified_synthesis') as verified_synthesis,
  (select count(*)::integer from public.project_core_semantic_truth_status t where t.project_id=p.id and t.truth_state='human_confirmed') as human_confirmed,
  (select count(*)::integer from public.project_core_semantic_truth_status t where t.project_id=p.id and t.truth_state='review_required') as review_required,
  (select count(*)::integer from public.project_core_semantic_truth_status t where t.project_id=p.id and t.truth_state='unsupported') as unsupported,
  (
    select count(*)::integer
    from public.semantic_observations so
    where so.project_id=p.id and so.domain_hint in ('strategy','creative','experience','journey') and so.status <> 'superseded'
  ) as semantic_observations,
  (
    select count(*)::integer
    from public.semantic_observations so
    where so.project_id=p.id and so.domain_hint in ('strategy','creative','experience','journey') and so.status='open'
  ) as semantic_observations_open,
  (
    select count(*)::integer
    from public.knowledge_relations kr
    join public.knowledge_entities pe on pe.id=kr.scope_entity_id
    where pe.domain_table='projects' and pe.domain_id=p.id and kr.status='active' and kr.relation_kind='fact'
      and coalesce(kr.attributes->>'normalized_by','')='V28.7.2B'
  ) as fact_relations,
  (
    select count(*)::integer
    from public.knowledge_relations kr
    join public.knowledge_entities pe on pe.id=kr.scope_entity_id
    where pe.domain_table='projects' and pe.domain_id=p.id and kr.status='active' and kr.relation_kind='inference'
      and coalesce(kr.attributes->>'normalized_by','')='V28.7.2B'
  ) as inference_relations,
  (select migration_mode from public.project_domain_migration_state m where m.project_id=p.id) as migration_mode,
  (select domain_schema_version from public.project_domain_migration_state m where m.project_id=p.id) as domain_schema_version,
  (select last_completed_run_id from public.project_domain_migration_state m where m.project_id=p.id) as last_completed_run_id
from public.projects p;

-- --------------------------------------------------------------------------
-- 7. Atomic writer.
-- --------------------------------------------------------------------------
create or replace function public.apply_project_core_semantics_v2872b(
  p_project_id uuid,
  p_run_id uuid,
  p_bundle jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  v_item jsonb;
  v_resolution jsonb;
  v_ev jsonb;
  v_project_entity_id uuid;
  v_domain_id uuid;
  v_entity_id uuid;
  v_context_sha text;
  v_observation_count integer := 0;
  v_strategy_count integer := 0;
  v_platform_count integer := 0;
  v_creative_element_count integer := 0;
  v_experience_count integer := 0;
  v_journey_count integer := 0;
  v_relation_count integer := 0;
begin
  if not exists (select 1 from public.projects where id=p_project_id) then
    raise exception 'V28.7.2B: projeto % não existe', p_project_id;
  end if;
  if not exists (select 1 from public.intelligence_runs where id=p_run_id) then
    raise exception 'V28.7.2B: intelligence_run % não existe', p_run_id;
  end if;
  v_project_entity_id := nullif(p_bundle->>'project_entity_id','')::uuid;
  if v_project_entity_id is null then
    raise exception 'V28.7.2B: project_entity_id ausente';
  end if;

  -- Observations first: staging/lineage before ontology commitment.
  for v_item in select value from jsonb_array_elements(coalesce(p_bundle->'observations','[]'::jsonb))
  loop
    insert into public.semantic_observations(
      id, project_id, source_asset_id, evidence_unit_id,
      observation_kind, observed_name, observed_type, observed_status,
      occurrence_phase, occurrence_role, domain_hint, semantic_role, assertion_mode,
      attributes, source_authority_score, model_confidence, extraction_method,
      observation_hash, status, resolution_action, intelligence_run_id
    ) values (
      (v_item->>'id')::uuid, p_project_id,
      (v_item->>'source_asset_id')::uuid, (v_item->>'evidence_unit_id')::uuid,
      v_item->>'observation_kind', v_item->>'observed_name', nullif(v_item->>'observed_type',''), nullif(v_item->>'observed_status',''),
      coalesce(nullif(v_item->>'occurrence_phase',''),'reference'), coalesce(nullif(v_item->>'occurrence_role',''),'mention'),
      nullif(v_item->>'domain_hint',''), nullif(v_item->>'semantic_role',''), nullif(v_item->>'assertion_mode',''),
      coalesce(v_item->'attributes','{}'::jsonb),
      nullif(v_item->>'source_authority_score','')::numeric, nullif(v_item->>'model_confidence','')::numeric,
      coalesce(nullif(v_item->>'extraction_method',''),'core_semantic_explicit_evidence'),
      v_item->>'observation_hash', 'open', 'none', p_run_id
    )
    on conflict (observation_hash) do update set
      observed_name=excluded.observed_name,
      observed_type=excluded.observed_type,
      occurrence_phase=excluded.occurrence_phase,
      occurrence_role=excluded.occurrence_role,
      domain_hint=excluded.domain_hint,
      semantic_role=excluded.semantic_role,
      assertion_mode=excluded.assertion_mode,
      attributes=coalesce(public.semantic_observations.attributes,'{}'::jsonb) || excluded.attributes,
      source_authority_score=greatest(coalesce(public.semantic_observations.source_authority_score,0),coalesce(excluded.source_authority_score,0)),
      model_confidence=greatest(coalesce(public.semantic_observations.model_confidence,0),coalesce(excluded.model_confidence,0)),
      intelligence_run_id=excluded.intelligence_run_id,
      updated_at=now();
    v_observation_count := v_observation_count + 1;
  end loop;

  -- Strategy Elements.
  for v_item in select value from jsonb_array_elements(coalesce(p_bundle->'strategy_elements','[]'::jsonb))
  loop
    v_domain_id := (v_item->>'id')::uuid;
    v_entity_id := (v_item->>'entity_id')::uuid;
    insert into public.knowledge_entities(
      id, entity_type, canonical_name, normalized_name, entity_kind, scope_entity_id,
      domain_table, domain_id, attributes, status, confidence
    ) values (
      v_entity_id,'strategy_element',v_item->>'title',lower(v_item->>'title'),'project_instance',v_project_entity_id,
      'project_strategy_elements',v_domain_id,jsonb_build_object('projection_only',true,'normalized_by','V28.7.2B'),'active',nullif(v_item->>'confidence','')::numeric
    )
    on conflict (domain_table,domain_id) where domain_table is not null and domain_id is not null
    do update set canonical_name=excluded.canonical_name,normalized_name=excluded.normalized_name,
      attributes=coalesce(public.knowledge_entities.attributes,'{}'::jsonb)||excluded.attributes,
      confidence=greatest(coalesce(public.knowledge_entities.confidence,0),coalesce(excluded.confidence,0)),updated_at=now();

    insert into public.project_strategy_elements(
      id,project_id,entity_id,strategy_key,strategy_type,title,statement,assertion_mode,scope,attributes,
      source_observation_id,source_evidence_id,confidence,authority_score,lifecycle_status,normalization_run_id
    ) values (
      v_domain_id,p_project_id,v_entity_id,v_item->>'strategy_key',v_item->>'strategy_type',v_item->>'title',v_item->>'statement',v_item->>'assertion_mode',
      coalesce(v_item->'scope','{}'::jsonb),coalesce(v_item->'attributes','{}'::jsonb),
      nullif(v_item->>'source_observation_id','')::uuid,(v_item->>'source_evidence_id')::uuid,
      nullif(v_item->>'confidence','')::numeric,nullif(v_item->>'authority_score','')::numeric,'active',p_run_id
    )
    on conflict (project_id,strategy_key) do update set
      title=excluded.title,
      statement=case when excluded.authority_score>=coalesce(public.project_strategy_elements.authority_score,0) then excluded.statement else public.project_strategy_elements.statement end,
      assertion_mode=excluded.assertion_mode,
      scope=coalesce(public.project_strategy_elements.scope,'{}'::jsonb)||excluded.scope,
      attributes=coalesce(public.project_strategy_elements.attributes,'{}'::jsonb)||excluded.attributes,
      source_observation_id=coalesce(excluded.source_observation_id,public.project_strategy_elements.source_observation_id),
      source_evidence_id=coalesce(excluded.source_evidence_id,public.project_strategy_elements.source_evidence_id),
      confidence=greatest(coalesce(public.project_strategy_elements.confidence,0),coalesce(excluded.confidence,0)),
      authority_score=greatest(coalesce(public.project_strategy_elements.authority_score,0),coalesce(excluded.authority_score,0)),
      lifecycle_status='active',normalization_run_id=p_run_id,updated_at=now();

    insert into public.domain_object_governance(entity_id,project_id,lifecycle_status,review_status,source_authority_score,model_confidence,field_authority,last_normalization_run_id,metadata)
    values(v_entity_id,p_project_id,'active','unreviewed',nullif(v_item->>'authority_score','')::numeric,nullif(v_item->>'confidence','')::numeric,
      jsonb_build_object('statement',coalesce(nullif(v_item->>'authority_score','')::numeric,0)),p_run_id,jsonb_build_object('normalized_by','V28.7.2B','domain','strategy'))
    on conflict(entity_id) do update set source_authority_score=greatest(coalesce(public.domain_object_governance.source_authority_score,0),coalesce(excluded.source_authority_score,0)),
      model_confidence=greatest(coalesce(public.domain_object_governance.model_confidence,0),coalesce(excluded.model_confidence,0)),last_normalization_run_id=p_run_id,
      metadata=coalesce(public.domain_object_governance.metadata,'{}'::jsonb)||excluded.metadata,updated_at=now();

    for v_ev in select value from jsonb_array_elements(coalesce(v_item->'evidence_ids',jsonb_build_array(v_item->>'source_evidence_id')))
    loop
      if nullif(trim(both '"' from v_ev::text),'') is not null then
        v_context_sha := encode(digest(jsonb_build_object('strategy_key',v_item->>'strategy_key')::text,'sha256'),'hex');
        insert into public.domain_object_evidence(project_id,object_entity_id,domain_table,domain_id,evidence_unit_id,link_role,context,context_sha256,binding_confidence,normalization_run_id)
        values(p_project_id,v_entity_id,'project_strategy_elements',v_domain_id,(trim(both '"' from v_ev::text))::uuid,'source',jsonb_build_object('strategy_key',v_item->>'strategy_key'),v_context_sha,nullif(v_item->>'confidence','')::numeric,p_run_id)
        on conflict(object_entity_id,evidence_unit_id,link_role,context_sha256) do update set binding_confidence=greatest(coalesce(public.domain_object_evidence.binding_confidence,0),coalesce(excluded.binding_confidence,0)),normalization_run_id=p_run_id,updated_at=now();
      end if;
    end loop;
    v_strategy_count := v_strategy_count + 1;
  end loop;

  -- Creative Platforms.
  for v_item in select value from jsonb_array_elements(coalesce(p_bundle->'creative_platforms','[]'::jsonb))
  loop
    v_domain_id := (v_item->>'id')::uuid; v_entity_id := (v_item->>'entity_id')::uuid;
    insert into public.knowledge_entities(id,entity_type,canonical_name,normalized_name,entity_kind,scope_entity_id,domain_table,domain_id,attributes,status,confidence)
    values(v_entity_id,'creative_platform',v_item->>'name',lower(v_item->>'name'),'project_instance',v_project_entity_id,'project_creative_platforms',v_domain_id,
      jsonb_build_object('projection_only',true,'normalized_by','V28.7.2B'),'active',nullif(v_item->>'confidence','')::numeric)
    on conflict(domain_table,domain_id) where domain_table is not null and domain_id is not null
    do update set canonical_name=excluded.canonical_name,normalized_name=excluded.normalized_name,attributes=coalesce(public.knowledge_entities.attributes,'{}'::jsonb)||excluded.attributes,
      confidence=greatest(coalesce(public.knowledge_entities.confidence,0),coalesce(excluded.confidence,0)),updated_at=now();

    insert into public.project_creative_platforms(id,project_id,entity_id,platform_key,name,description,assertion_mode,attributes,source_observation_id,source_evidence_id,confidence,authority_score,lifecycle_status,normalization_run_id)
    values(v_domain_id,p_project_id,v_entity_id,v_item->>'platform_key',v_item->>'name',nullif(v_item->>'description',''),v_item->>'assertion_mode',coalesce(v_item->'attributes','{}'::jsonb),
      nullif(v_item->>'source_observation_id','')::uuid,(v_item->>'source_evidence_id')::uuid,nullif(v_item->>'confidence','')::numeric,nullif(v_item->>'authority_score','')::numeric,'active',p_run_id)
    on conflict(project_id,platform_key) do update set name=excluded.name,description=case when excluded.authority_score>=coalesce(public.project_creative_platforms.authority_score,0) then excluded.description else public.project_creative_platforms.description end,
      assertion_mode=excluded.assertion_mode,attributes=coalesce(public.project_creative_platforms.attributes,'{}'::jsonb)||excluded.attributes,
      confidence=greatest(coalesce(public.project_creative_platforms.confidence,0),coalesce(excluded.confidence,0)),authority_score=greatest(coalesce(public.project_creative_platforms.authority_score,0),coalesce(excluded.authority_score,0)),
      lifecycle_status='active',normalization_run_id=p_run_id,updated_at=now();

    insert into public.domain_object_governance(entity_id,project_id,lifecycle_status,review_status,source_authority_score,model_confidence,field_authority,last_normalization_run_id,metadata)
    values(v_entity_id,p_project_id,'active','unreviewed',nullif(v_item->>'authority_score','')::numeric,nullif(v_item->>'confidence','')::numeric,jsonb_build_object('name',coalesce(nullif(v_item->>'authority_score','')::numeric,0)),p_run_id,jsonb_build_object('normalized_by','V28.7.2B','domain','creative_platform'))
    on conflict(entity_id) do update set source_authority_score=greatest(coalesce(public.domain_object_governance.source_authority_score,0),coalesce(excluded.source_authority_score,0)),model_confidence=greatest(coalesce(public.domain_object_governance.model_confidence,0),coalesce(excluded.model_confidence,0)),last_normalization_run_id=p_run_id,metadata=coalesce(public.domain_object_governance.metadata,'{}'::jsonb)||excluded.metadata,updated_at=now();

    for v_ev in select value from jsonb_array_elements(coalesce(v_item->'evidence_ids',jsonb_build_array(v_item->>'source_evidence_id')))
    loop
      v_context_sha := encode(digest(jsonb_build_object('platform_key',v_item->>'platform_key')::text,'sha256'),'hex');
      insert into public.domain_object_evidence(project_id,object_entity_id,domain_table,domain_id,evidence_unit_id,link_role,context,context_sha256,binding_confidence,normalization_run_id)
      values(p_project_id,v_entity_id,'project_creative_platforms',v_domain_id,(trim(both '"' from v_ev::text))::uuid,'source',jsonb_build_object('platform_key',v_item->>'platform_key'),v_context_sha,nullif(v_item->>'confidence','')::numeric,p_run_id)
      on conflict(object_entity_id,evidence_unit_id,link_role,context_sha256) do update set binding_confidence=greatest(coalesce(public.domain_object_evidence.binding_confidence,0),coalesce(excluded.binding_confidence,0)),normalization_run_id=p_run_id,updated_at=now();
    end loop;
    v_platform_count := v_platform_count + 1;
  end loop;

  -- Creative Elements.
  for v_item in select value from jsonb_array_elements(coalesce(p_bundle->'creative_elements','[]'::jsonb))
  loop
    v_domain_id := (v_item->>'id')::uuid; v_entity_id := (v_item->>'entity_id')::uuid;
    insert into public.knowledge_entities(id,entity_type,canonical_name,normalized_name,entity_kind,scope_entity_id,domain_table,domain_id,attributes,status,confidence)
    values(v_entity_id,'creative_element',v_item->>'title',lower(v_item->>'title'),'project_instance',v_project_entity_id,'project_creative_elements',v_domain_id,
      jsonb_build_object('projection_only',true,'normalized_by','V28.7.2B'),'active',nullif(v_item->>'confidence','')::numeric)
    on conflict(domain_table,domain_id) where domain_table is not null and domain_id is not null
    do update set canonical_name=excluded.canonical_name,normalized_name=excluded.normalized_name,confidence=greatest(coalesce(public.knowledge_entities.confidence,0),coalesce(excluded.confidence,0)),updated_at=now();

    insert into public.project_creative_elements(id,project_id,platform_id,entity_id,element_key,creative_type,title,statement,assertion_mode,attributes,source_observation_id,source_evidence_id,confidence,authority_score,lifecycle_status,normalization_run_id)
    values(v_domain_id,p_project_id,(v_item->>'platform_id')::uuid,v_entity_id,v_item->>'element_key',v_item->>'creative_type',v_item->>'title',v_item->>'statement',v_item->>'assertion_mode',coalesce(v_item->'attributes','{}'::jsonb),
      nullif(v_item->>'source_observation_id','')::uuid,(v_item->>'source_evidence_id')::uuid,nullif(v_item->>'confidence','')::numeric,nullif(v_item->>'authority_score','')::numeric,'active',p_run_id)
    on conflict(project_id,element_key) do update set title=excluded.title,statement=case when excluded.authority_score>=coalesce(public.project_creative_elements.authority_score,0) then excluded.statement else public.project_creative_elements.statement end,
      assertion_mode=excluded.assertion_mode,attributes=coalesce(public.project_creative_elements.attributes,'{}'::jsonb)||excluded.attributes,
      confidence=greatest(coalesce(public.project_creative_elements.confidence,0),coalesce(excluded.confidence,0)),authority_score=greatest(coalesce(public.project_creative_elements.authority_score,0),coalesce(excluded.authority_score,0)),lifecycle_status='active',normalization_run_id=p_run_id,updated_at=now();

    insert into public.domain_object_governance(entity_id,project_id,lifecycle_status,review_status,source_authority_score,model_confidence,field_authority,last_normalization_run_id,metadata)
    values(v_entity_id,p_project_id,'active','unreviewed',nullif(v_item->>'authority_score','')::numeric,nullif(v_item->>'confidence','')::numeric,jsonb_build_object('statement',coalesce(nullif(v_item->>'authority_score','')::numeric,0)),p_run_id,jsonb_build_object('normalized_by','V28.7.2B','domain','creative_element'))
    on conflict(entity_id) do update set source_authority_score=greatest(coalesce(public.domain_object_governance.source_authority_score,0),coalesce(excluded.source_authority_score,0)),model_confidence=greatest(coalesce(public.domain_object_governance.model_confidence,0),coalesce(excluded.model_confidence,0)),last_normalization_run_id=p_run_id,metadata=coalesce(public.domain_object_governance.metadata,'{}'::jsonb)||excluded.metadata,updated_at=now();

    for v_ev in select value from jsonb_array_elements(coalesce(v_item->'evidence_ids',jsonb_build_array(v_item->>'source_evidence_id')))
    loop
      v_context_sha := encode(digest(jsonb_build_object('element_key',v_item->>'element_key')::text,'sha256'),'hex');
      insert into public.domain_object_evidence(project_id,object_entity_id,domain_table,domain_id,evidence_unit_id,link_role,context,context_sha256,binding_confidence,normalization_run_id)
      values(p_project_id,v_entity_id,'project_creative_elements',v_domain_id,(trim(both '"' from v_ev::text))::uuid,'source',jsonb_build_object('element_key',v_item->>'element_key'),v_context_sha,nullif(v_item->>'confidence','')::numeric,p_run_id)
      on conflict(object_entity_id,evidence_unit_id,link_role,context_sha256) do update set binding_confidence=greatest(coalesce(public.domain_object_evidence.binding_confidence,0),coalesce(excluded.binding_confidence,0)),normalization_run_id=p_run_id,updated_at=now();
    end loop;
    v_creative_element_count := v_creative_element_count + 1;
  end loop;

  -- Experience Architectures.
  for v_item in select value from jsonb_array_elements(coalesce(p_bundle->'experience_architectures','[]'::jsonb))
  loop
    v_domain_id := (v_item->>'id')::uuid; v_entity_id := (v_item->>'entity_id')::uuid;
    insert into public.knowledge_entities(id,entity_type,canonical_name,normalized_name,entity_kind,scope_entity_id,domain_table,domain_id,attributes,status,confidence)
    values(v_entity_id,'experience_architecture',v_item->>'name',lower(v_item->>'name'),'project_instance',v_project_entity_id,'project_experience_architectures',v_domain_id,
      jsonb_build_object('projection_only',true,'normalized_by','V28.7.2B'),'active',nullif(v_item->>'confidence','')::numeric)
    on conflict(domain_table,domain_id) where domain_table is not null and domain_id is not null
    do update set canonical_name=excluded.canonical_name,normalized_name=excluded.normalized_name,confidence=greatest(coalesce(public.knowledge_entities.confidence,0),coalesce(excluded.confidence,0)),updated_at=now();

    insert into public.project_experience_architectures(id,project_id,entity_id,architecture_key,name,experience_principle,participation_logic,flow_summary,assertion_mode,attributes,source_observation_id,source_evidence_id,confidence,authority_score,lifecycle_status,normalization_run_id)
    values(v_domain_id,p_project_id,v_entity_id,v_item->>'architecture_key',v_item->>'name',nullif(v_item->>'experience_principle',''),nullif(v_item->>'participation_logic',''),nullif(v_item->>'flow_summary',''),v_item->>'assertion_mode',coalesce(v_item->'attributes','{}'::jsonb),
      nullif(v_item->>'source_observation_id','')::uuid,(v_item->>'source_evidence_id')::uuid,nullif(v_item->>'confidence','')::numeric,nullif(v_item->>'authority_score','')::numeric,'active',p_run_id)
    on conflict(project_id,architecture_key) do update set name=excluded.name,flow_summary=case when excluded.authority_score>=coalesce(public.project_experience_architectures.authority_score,0) then excluded.flow_summary else public.project_experience_architectures.flow_summary end,
      assertion_mode=excluded.assertion_mode,attributes=coalesce(public.project_experience_architectures.attributes,'{}'::jsonb)||excluded.attributes,
      confidence=greatest(coalesce(public.project_experience_architectures.confidence,0),coalesce(excluded.confidence,0)),authority_score=greatest(coalesce(public.project_experience_architectures.authority_score,0),coalesce(excluded.authority_score,0)),lifecycle_status='active',normalization_run_id=p_run_id,updated_at=now();

    insert into public.domain_object_governance(entity_id,project_id,lifecycle_status,review_status,source_authority_score,model_confidence,field_authority,last_normalization_run_id,metadata)
    values(v_entity_id,p_project_id,'active','unreviewed',nullif(v_item->>'authority_score','')::numeric,nullif(v_item->>'confidence','')::numeric,jsonb_build_object('flow_summary',coalesce(nullif(v_item->>'authority_score','')::numeric,0)),p_run_id,jsonb_build_object('normalized_by','V28.7.2B','domain','experience'))
    on conflict(entity_id) do update set source_authority_score=greatest(coalesce(public.domain_object_governance.source_authority_score,0),coalesce(excluded.source_authority_score,0)),model_confidence=greatest(coalesce(public.domain_object_governance.model_confidence,0),coalesce(excluded.model_confidence,0)),last_normalization_run_id=p_run_id,metadata=coalesce(public.domain_object_governance.metadata,'{}'::jsonb)||excluded.metadata,updated_at=now();

    for v_ev in select value from jsonb_array_elements(coalesce(v_item->'evidence_ids',jsonb_build_array(v_item->>'source_evidence_id')))
    loop
      v_context_sha := encode(digest(jsonb_build_object('architecture_key',v_item->>'architecture_key')::text,'sha256'),'hex');
      insert into public.domain_object_evidence(project_id,object_entity_id,domain_table,domain_id,evidence_unit_id,link_role,context,context_sha256,binding_confidence,normalization_run_id)
      values(p_project_id,v_entity_id,'project_experience_architectures',v_domain_id,(trim(both '"' from v_ev::text))::uuid,'source',jsonb_build_object('architecture_key',v_item->>'architecture_key'),v_context_sha,nullif(v_item->>'confidence','')::numeric,p_run_id)
      on conflict(object_entity_id,evidence_unit_id,link_role,context_sha256) do update set binding_confidence=greatest(coalesce(public.domain_object_evidence.binding_confidence,0),coalesce(excluded.binding_confidence,0)),normalization_run_id=p_run_id,updated_at=now();
    end loop;
    v_experience_count := v_experience_count + 1;
  end loop;

  -- Journey Moments.
  for v_item in select value from jsonb_array_elements(coalesce(p_bundle->'journey_moments','[]'::jsonb))
  loop
    v_domain_id := (v_item->>'id')::uuid; v_entity_id := (v_item->>'entity_id')::uuid;
    insert into public.knowledge_entities(id,entity_type,canonical_name,normalized_name,entity_kind,scope_entity_id,domain_table,domain_id,attributes,status,confidence)
    values(v_entity_id,'journey_moment',v_item->>'title',lower(v_item->>'title'),'project_instance',v_project_entity_id,'project_journey_moments',v_domain_id,
      jsonb_build_object('projection_only',true,'normalized_by','V28.7.2B'),'active',nullif(v_item->>'confidence','')::numeric)
    on conflict(domain_table,domain_id) where domain_table is not null and domain_id is not null
    do update set canonical_name=excluded.canonical_name,normalized_name=excluded.normalized_name,confidence=greatest(coalesce(public.knowledge_entities.confidence,0),coalesce(excluded.confidence,0)),updated_at=now();

    insert into public.project_journey_moments(id,project_id,architecture_id,entity_id,moment_key,sequence_index,moment_type,title,purpose,participant_action,experience_role,assertion_mode,architecture_association_mode,attributes,source_observation_id,source_evidence_id,confidence,authority_score,lifecycle_status,normalization_run_id)
    values(v_domain_id,p_project_id,(v_item->>'architecture_id')::uuid,v_entity_id,v_item->>'moment_key',nullif(v_item->>'sequence_index','')::integer,v_item->>'moment_type',v_item->>'title',nullif(v_item->>'purpose',''),nullif(v_item->>'participant_action',''),nullif(v_item->>'experience_role',''),v_item->>'assertion_mode',coalesce(nullif(v_item->>'architecture_association_mode',''),'source_explicit'),coalesce(v_item->'attributes','{}'::jsonb),
      nullif(v_item->>'source_observation_id','')::uuid,(v_item->>'source_evidence_id')::uuid,nullif(v_item->>'confidence','')::numeric,nullif(v_item->>'authority_score','')::numeric,'active',p_run_id)
    on conflict(project_id,moment_key) do update set sequence_index=coalesce(excluded.sequence_index,public.project_journey_moments.sequence_index),title=excluded.title,purpose=case when excluded.authority_score>=coalesce(public.project_journey_moments.authority_score,0) then excluded.purpose else public.project_journey_moments.purpose end,
      assertion_mode=excluded.assertion_mode,architecture_association_mode=excluded.architecture_association_mode,attributes=coalesce(public.project_journey_moments.attributes,'{}'::jsonb)||excluded.attributes,
      confidence=greatest(coalesce(public.project_journey_moments.confidence,0),coalesce(excluded.confidence,0)),authority_score=greatest(coalesce(public.project_journey_moments.authority_score,0),coalesce(excluded.authority_score,0)),lifecycle_status='active',normalization_run_id=p_run_id,updated_at=now();

    insert into public.domain_object_governance(entity_id,project_id,lifecycle_status,review_status,source_authority_score,model_confidence,field_authority,last_normalization_run_id,metadata)
    values(v_entity_id,p_project_id,'active','unreviewed',nullif(v_item->>'authority_score','')::numeric,nullif(v_item->>'confidence','')::numeric,jsonb_build_object('purpose',coalesce(nullif(v_item->>'authority_score','')::numeric,0)),p_run_id,jsonb_build_object('normalized_by','V28.7.2B','domain','journey'))
    on conflict(entity_id) do update set source_authority_score=greatest(coalesce(public.domain_object_governance.source_authority_score,0),coalesce(excluded.source_authority_score,0)),model_confidence=greatest(coalesce(public.domain_object_governance.model_confidence,0),coalesce(excluded.model_confidence,0)),last_normalization_run_id=p_run_id,metadata=coalesce(public.domain_object_governance.metadata,'{}'::jsonb)||excluded.metadata,updated_at=now();

    for v_ev in select value from jsonb_array_elements(coalesce(v_item->'evidence_ids',jsonb_build_array(v_item->>'source_evidence_id')))
    loop
      v_context_sha := encode(digest(jsonb_build_object('moment_key',v_item->>'moment_key')::text,'sha256'),'hex');
      insert into public.domain_object_evidence(project_id,object_entity_id,domain_table,domain_id,evidence_unit_id,link_role,context,context_sha256,binding_confidence,normalization_run_id)
      values(p_project_id,v_entity_id,'project_journey_moments',v_domain_id,(trim(both '"' from v_ev::text))::uuid,'source',jsonb_build_object('moment_key',v_item->>'moment_key'),v_context_sha,nullif(v_item->>'confidence','')::numeric,p_run_id)
      on conflict(object_entity_id,evidence_unit_id,link_role,context_sha256) do update set binding_confidence=greatest(coalesce(public.domain_object_evidence.binding_confidence,0),coalesce(excluded.binding_confidence,0)),normalization_run_id=p_run_id,updated_at=now();
    end loop;
    v_journey_count := v_journey_count + 1;
  end loop;

  -- Relations and N:N relation provenance.
  for v_item in select value from jsonb_array_elements(coalesce(p_bundle->'relations','[]'::jsonb))
  loop
    insert into public.knowledge_relations(
      id,source_entity_id,relation_type,target_entity_id,scope_entity_id,relation_kind,strength,confidence,authority_score,status,attributes,intelligence_run_id,relation_hash
    ) values (
      (v_item->>'id')::uuid,(v_item->>'source_entity_id')::uuid,v_item->>'relation_type',(v_item->>'target_entity_id')::uuid,
      v_project_entity_id,coalesce(nullif(v_item->>'relation_kind',''),'fact'),nullif(v_item->>'strength','')::numeric,
      nullif(v_item->>'confidence','')::numeric,nullif(v_item->>'authority_score','')::numeric,coalesce(nullif(v_item->>'status',''),'active'),
      coalesce(v_item->'attributes','{}'::jsonb),p_run_id,v_item->>'relation_hash'
    )
    on conflict(relation_hash) do update set
      confidence=greatest(coalesce(public.knowledge_relations.confidence,0),coalesce(excluded.confidence,0)),
      authority_score=greatest(coalesce(public.knowledge_relations.authority_score,0),coalesce(excluded.authority_score,0)),
      status=excluded.status,attributes=coalesce(public.knowledge_relations.attributes,'{}'::jsonb)||excluded.attributes,
      intelligence_run_id=p_run_id,updated_at=now();

    for v_ev in select value from jsonb_array_elements(coalesce(v_item->'evidence_unit_ids','[]'::jsonb))
    loop
      insert into public.relation_evidence(relation_id,evidence_unit_id,support_type,evidence_weight)
      values((v_item->>'id')::uuid,(trim(both '"' from v_ev::text))::uuid,'supports',coalesce(nullif(v_item->>'evidence_weight','')::numeric,1))
      on conflict(relation_id,evidence_unit_id,support_type) do update set evidence_weight=greatest(public.relation_evidence.evidence_weight,excluded.evidence_weight);
    end loop;
    v_relation_count := v_relation_count + 1;
  end loop;

  -- Observation resolution only after all referenced domain rows exist.
  for v_resolution in select value from jsonb_array_elements(coalesce(p_bundle->'observation_resolutions','[]'::jsonb))
  loop
    update public.semantic_observations
    set status=coalesce(nullif(v_resolution->>'status',''),'open'),
        resolution_action=coalesce(nullif(v_resolution->>'resolution_action',''),'none'),
        resolved_entity_id=nullif(v_resolution->>'resolved_entity_id','')::uuid,
        resolved_domain_table=nullif(v_resolution->>'resolved_domain_table',''),
        resolved_domain_id=nullif(v_resolution->>'resolved_domain_id','')::uuid,
        resolution_detail=coalesce(v_resolution->'resolution_detail','{}'::jsonb),
        resolution_run_id=p_run_id,
        updated_at=now()
    where id=(v_resolution->>'id')::uuid;
  end loop;

  -- Shadow stays shadow. B advances schema only.
  insert into public.project_domain_migration_state(project_id,migration_mode,domain_schema_version,last_completed_run_id)
  values(p_project_id,'legacy_shadow','28.7.2b',p_run_id)
  on conflict(project_id) do update set migration_mode='legacy_shadow',domain_schema_version='28.7.2b',last_completed_run_id=p_run_id,updated_at=now();

  update public.intelligence_runs
  set status='completed',completed_at=now(),
      output_signature=encode(digest(jsonb_build_object(
        'observations',v_observation_count,'strategy',v_strategy_count,'creative_platforms',v_platform_count,
        'creative_elements',v_creative_element_count,'experience',v_experience_count,'journey',v_journey_count,'relations',v_relation_count
      )::text,'sha256'),'hex'),
      metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
        'observations',v_observation_count,'strategy_elements',v_strategy_count,'creative_platforms',v_platform_count,
        'creative_elements',v_creative_element_count,'experience_architectures',v_experience_count,'journey_moments',v_journey_count,
        'relations',v_relation_count,'migration_mode','legacy_shadow','analyst_inference_as_truth',false
      )
  where id=p_run_id;

  return jsonb_build_object(
    'status','completed','project_id',p_project_id,'run_id',p_run_id,
    'observations',v_observation_count,'strategy_elements',v_strategy_count,
    'creative_platforms',v_platform_count,'creative_elements',v_creative_element_count,
    'experience_architectures',v_experience_count,'journey_moments',v_journey_count,
    'relations',v_relation_count,'migration_mode','legacy_shadow'
  );
end;
$$;

revoke all on function public.apply_project_core_semantics_v2872b(uuid,uuid,jsonb) from public, anon, authenticated;
grant execute on function public.apply_project_core_semantics_v2872b(uuid,uuid,jsonb) to service_role, postgres;

-- --------------------------------------------------------------------------
-- 8. Private server-side permissions.
-- --------------------------------------------------------------------------
do $$
declare t text;
begin
  foreach t in array array[
    'project_strategy_elements','project_creative_platforms','project_creative_elements',
    'project_experience_architectures','project_journey_moments'
  ] loop
    execute format('alter table public.%I enable row level security',t);
    execute format('revoke all on public.%I from anon, authenticated',t);
    execute format('grant select, insert, update, delete on public.%I to service_role, postgres',t);
  end loop;
end $$;

revoke all on public.project_core_semantic_truth_status from anon, authenticated;
revoke all on public.project_core_semantic_status from anon, authenticated;
grant select on public.project_core_semantic_truth_status to service_role, postgres;
grant select on public.project_core_semantic_status to service_role, postgres;

comment on table public.project_strategy_elements is 'V28.7.2B Strategy Domain: evidence-backed strategic objects, distinct from Solutions and Analyst synthesis.';
comment on table public.project_creative_platforms is 'V28.7.2B Creative Platform / Concept System identity.';
comment on table public.project_creative_elements is 'V28.7.2B typed elements belonging to a Creative Platform.';
comment on table public.project_experience_architectures is 'V28.7.2B evidence-backed architecture/orchestration of an experience.';
comment on table public.project_journey_moments is 'V28.7.2B stages/moments/touchpoints. Journey is not a Project Solution.';
comment on view public.project_core_semantic_truth_status is 'Semantic Truth Gate for Strategy/Creative/Experience. Analyst inference is never promoted as Domain Truth.';

-- --------------------------------------------------------------------------
-- 9. Install checks — no cutover.
-- --------------------------------------------------------------------------
do $$
begin
  if to_regclass('public.project_strategy_elements') is null
     or to_regclass('public.project_creative_platforms') is null
     or to_regclass('public.project_creative_elements') is null
     or to_regclass('public.project_experience_architectures') is null
     or to_regclass('public.project_journey_moments') is null then
    raise exception 'V28.7.2B install check failed: core semantic domain table missing';
  end if;
  if to_regclass('public.project_core_semantic_truth_status') is null
     or to_regclass('public.project_core_semantic_status') is null then
    raise exception 'V28.7.2B install check failed: semantic status view missing';
  end if;
  if not exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='semantic_observations' and column_name='assertion_mode'
  ) then
    raise exception 'V28.7.2B install check failed: semantic_observations assertion_mode missing';
  end if;
end $$;

commit;
