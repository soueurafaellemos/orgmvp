begin;

-- ============================================================================
-- NAVE by VOE · V28.7.2A — RECONCILIATION KERNEL, CONTEXT & SOLUTION LIFECYCLE
--
-- Additive semantic-domain layer over the approved V28.7.1D Truth Gate.
-- No domain_primary cutover. V28.6 Graph stays frozen by runtime orchestration.
--
-- Contracts:
--  1) Evidence -> Semantic Observation -> Reconciliation -> Domain;
--  2) an observation is not domain truth;
--  3) two existing Project Solution Instances are never auto-merged here;
--  4) evidence-backed execution creates occurrence first, then outcome;
--  5) logistical/material report rows may be preserved as no_domain_object;
--  6) Context is distinct from Requirement;
--  7) quantitative requirements preserve range and scope;
--  8) V28.7.1D current-truth resolver is not replaced by this migration;
--  9) migration_mode remains legacy_shadow.
-- ============================================================================

create extension if not exists pgcrypto;

-- --------------------------------------------------------------------------
-- 0. Prerequisites — fail before any change.
-- --------------------------------------------------------------------------
do $$
begin
  if to_regclass('public.project_solution_instances') is null
     or to_regclass('public.project_solution_occurrences') is null
     or to_regclass('public.project_requirements') is null
     or to_regclass('public.entity_outcomes') is null
     or to_regclass('public.project_domain_migration_state') is null then
    raise exception 'V28.7.2A prerequisite missing: V28.7 domain tables';
  end if;
  if to_regclass('public.source_assets') is null
     or to_regclass('public.evidence_units') is null
     or to_regclass('public.knowledge_entities') is null then
    raise exception 'V28.7.2A prerequisite missing: Intelligence Foundation';
  end if;
  if to_regclass('public.entity_outcome_truth_status') is null
     or to_regclass('public.entity_current_outcomes') is null then
    raise exception 'V28.7.2A prerequisite missing: V28.7.1D Truth Gate';
  end if;
  if to_regclass('public.domain_object_evidence') is null
     or to_regclass('public.domain_object_governance') is null then
    raise exception 'V28.7.2A prerequisite missing: Domain Integrity';
  end if;
  if to_regclass('public.intelligence_reviews') is null
     or to_regclass('public.intelligence_runs') is null then
    raise exception 'V28.7.2A prerequisite missing: review/run infrastructure';
  end if;
end $$;

-- --------------------------------------------------------------------------
-- 1. Ontology support for Context mirrors.
-- --------------------------------------------------------------------------
insert into public.ontology_entity_types(
  code, label_pt, label_en, parent_code,
  is_global_canonical, is_project_instance_allowed,
  description, active, schema_version
)
values (
  'context_element', 'Elemento de contexto', 'Context element', null,
  false, true,
  'Contexto de briefing/projeto evidence-backed, distinto de requirement e strategy.',
  true, 1
)
on conflict (code) do update set
  label_pt = excluded.label_pt,
  label_en = excluded.label_en,
  description = excluded.description,
  active = true,
  updated_at = now();

-- --------------------------------------------------------------------------
-- 2. Semantic Observations — staging auditável, nunca current truth.
-- --------------------------------------------------------------------------
create table if not exists public.semantic_observations (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  source_asset_id uuid not null references public.source_assets(id) on delete cascade,
  evidence_unit_id uuid not null references public.evidence_units(id) on delete cascade,

  observation_kind text not null
    check (observation_kind in (
      'solution_candidate','solution_mention','material_mention',
      'context_signal','requirement_signal','other'
    )),
  observed_name text not null,
  observed_type text,
  observed_status text,

  occurrence_phase text not null default 'reference'
    check (occurrence_phase in (
      'briefing','strategy','proposal','revision','approval','execution',
      'post_event','feedback','reference','manual','other'
    )),
  occurrence_role text not null default 'mention'
    check (occurrence_role in (
      'mention','proposal','budget_reference','execution','result',
      'feedback_context','visual','composition','reference','manual','other'
    )),

  attributes jsonb not null default '{}'::jsonb,
  source_authority_score numeric(5,4)
    check (source_authority_score is null or source_authority_score between 0 and 1),
  model_confidence numeric(5,4)
    check (model_confidence is null or model_confidence between 0 and 1),
  extraction_method text not null,

  observation_hash text not null unique,
  status text not null default 'open'
    check (status in ('open','reconciled','review_required','no_domain_object','dismissed','superseded')),

  resolved_entity_id uuid references public.knowledge_entities(id) on delete set null,
  resolved_domain_table text,
  resolved_domain_id uuid,
  resolution_action text not null default 'none'
    check (resolution_action in (
      'none','attach_occurrence','create_instance','review_required',
      'no_domain_object','insufficient_evidence'
    )),
  resolution_detail jsonb not null default '{}'::jsonb,
  resolution_run_id uuid references public.intelligence_runs(id) on delete set null,
  intelligence_run_id uuid references public.intelligence_runs(id) on delete set null,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists semantic_observations_project_idx
  on public.semantic_observations(project_id, status, observation_kind, created_at desc);
create index if not exists semantic_observations_evidence_idx
  on public.semantic_observations(evidence_unit_id, observation_kind);
create index if not exists semantic_observations_resolved_idx
  on public.semantic_observations(resolved_entity_id, status)
  where resolved_entity_id is not null;
create index if not exists semantic_observations_attributes_gin_idx
  on public.semantic_observations using gin(attributes);

-- --------------------------------------------------------------------------
-- 3. Project Context — Briefing is not only Requirements.
-- --------------------------------------------------------------------------
create table if not exists public.project_context_elements (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  entity_id uuid not null unique references public.knowledge_entities(id) on delete restrict,

  context_key text not null,
  context_type text not null
    check (context_type in (
      'business_context','brand_context','communication_problem','objective',
      'audience_context','geography','deadline_context','success_criterion',
      'assumption','background','other'
    )),
  title text not null,
  statement text not null,
  scope jsonb not null default '{}'::jsonb,
  attributes jsonb not null default '{}'::jsonb,

  source_claim_id uuid references public.knowledge_claims(id) on delete set null,
  source_evidence_id uuid references public.evidence_units(id) on delete set null,
  confidence numeric(5,4) check (confidence is null or confidence between 0 and 1),
  authority_score numeric(5,4) check (authority_score is null or authority_score between 0 and 1),
  lifecycle_status text not null default 'active'
    check (lifecycle_status in ('active','superseded','invalidated')),
  normalization_run_id uuid references public.intelligence_runs(id) on delete set null,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint project_context_elements_key_uidx unique(project_id, context_key)
);

create index if not exists project_context_elements_project_idx
  on public.project_context_elements(project_id, context_type, lifecycle_status, updated_at desc);

-- --------------------------------------------------------------------------
-- 4. Quantitative/scoped Requirement Constraints.
-- --------------------------------------------------------------------------
create table if not exists public.project_requirement_constraints (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  requirement_id uuid not null references public.project_requirements(id) on delete cascade,

  constraint_type text not null,
  operator text not null
    check (operator in ('=','<=','>=','between','in','must','must_not','envelope','range','unspecified','other')),

  value_numeric numeric,
  value_min numeric,
  value_max numeric,
  value_text text,
  value_json jsonb not null default '{}'::jsonb,
  unit text,
  currency text,

  scope_type text not null default 'project',
  scope_entity_id uuid references public.knowledge_entities(id) on delete set null,
  scope_json jsonb not null default '{}'::jsonb,

  source_evidence_id uuid not null references public.evidence_units(id) on delete restrict,
  confidence numeric(5,4) check (confidence is null or confidence between 0 and 1),
  authority_score numeric(5,4) check (authority_score is null or authority_score between 0 and 1),
  status text not null default 'active'
    check (status in ('active','superseded','invalidated')),
  constraint_hash text not null unique,
  normalization_run_id uuid references public.intelligence_runs(id) on delete set null,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint project_requirement_constraints_value_chk check (
    value_numeric is not null
    or value_min is not null
    or value_max is not null
    or value_text is not null
    or value_json <> '{}'::jsonb
  ),
  constraint project_requirement_constraints_range_chk check (
    value_min is null or value_max is null or value_max >= value_min
  )
);

create index if not exists project_requirement_constraints_project_idx
  on public.project_requirement_constraints(project_id, constraint_type, status);
create index if not exists project_requirement_constraints_requirement_idx
  on public.project_requirement_constraints(requirement_id, status);
create index if not exists project_requirement_constraints_scope_idx
  on public.project_requirement_constraints(scope_entity_id, constraint_type)
  where scope_entity_id is not null;

-- --------------------------------------------------------------------------
-- 5. Extend occurrence vocabulary; identity/occurrence table remains canonical.
-- --------------------------------------------------------------------------
alter table public.project_solution_occurrences
  drop constraint if exists project_solution_occurrences_occurrence_phase_check;
alter table public.project_solution_occurrences
  add constraint project_solution_occurrences_occurrence_phase_check
  check (occurrence_phase in (
    'briefing','strategy','proposal','revision','approval','execution',
    'post_event','feedback','reference','manual','other'
  ));

alter table public.project_solution_occurrences
  drop constraint if exists project_solution_occurrences_occurrence_role_check;
alter table public.project_solution_occurrences
  add constraint project_solution_occurrences_occurrence_role_check
  check (occurrence_role in (
    'mention','proposal','budget_reference','execution','result',
    'feedback_context','visual','composition','reference','manual','other'
  ));

-- --------------------------------------------------------------------------
-- 6. Human review can address the pre-domain observation itself.
-- --------------------------------------------------------------------------
alter table public.intelligence_reviews
  drop constraint if exists intelligence_reviews_object_type_check;
alter table public.intelligence_reviews
  add constraint intelligence_reviews_object_type_check
  check (object_type in (
    'entity','claim','relation','finding','feedback_claim','outcome',
    'entity_resolution','semantic_observation'
  ));

-- --------------------------------------------------------------------------
-- 7. Outcome lineage to Semantic Observation — additive; Truth Gate unchanged.
-- --------------------------------------------------------------------------
alter table public.entity_outcomes
  add column if not exists source_observation_id uuid
  references public.semantic_observations(id) on delete set null;

create unique index if not exists entity_outcomes_semantic_observation_uidx
  on public.entity_outcomes(source_observation_id, outcome_type, outcome_status)
  where source_observation_id is not null;

-- --------------------------------------------------------------------------
-- 8. Views for debugger/gates.
-- --------------------------------------------------------------------------
create or replace view public.project_semantic_observation_status
with (security_invoker = true)
as
select
  p.id as project_id,
  count(so.id)::integer as observations_total,
  count(so.id) filter (where so.status = 'open')::integer as observations_open,
  count(so.id) filter (where so.status = 'reconciled')::integer as observations_reconciled,
  count(so.id) filter (where so.status = 'review_required')::integer as observations_review_required,
  count(so.id) filter (where so.status = 'no_domain_object')::integer as observations_no_domain_object,
  count(so.id) filter (where so.observation_kind = 'solution_candidate')::integer as solution_candidates,
  count(so.id) filter (where so.observation_kind = 'material_mention')::integer as material_mentions
from public.projects p
left join public.semantic_observations so on so.project_id = p.id
  and so.status <> 'superseded'
  and exists (
    select 1 from public.evidence_units eu
    where eu.id = so.evidence_unit_id and eu.is_current = true
  )
group by p.id;

create or replace view public.project_domain_reconciliation_status
with (security_invoker = true)
as
select
  p.id as project_id,
  (select count(*)::integer from public.project_solution_instances psi where psi.project_id = p.id) as solution_instances,
  (
    select count(distinct pso.solution_instance_id)::integer
    from public.project_solution_occurrences pso
    where pso.project_id = p.id
      and pso.lifecycle_status = 'active'
      and pso.evidence_unit_id is not null
      and exists (select 1 from public.evidence_units eu where eu.id = pso.evidence_unit_id and eu.is_current = true)
      and pso.legacy_memory_item_id is null
  ) as evidence_reconciled_solutions,
  (
    select count(*)::integer
    from public.project_solution_instances psi
    where psi.project_id = p.id
      and coalesce(psi.attributes->>'origin','') = 'evidence_led_v2872a'
  ) as evidence_led_created_solutions,
  (
    select count(*)::integer
    from public.project_solution_occurrences pso
    where pso.project_id = p.id
      and pso.lifecycle_status = 'active'
      and pso.occurrence_role = 'execution'
      and pso.evidence_unit_id is not null
      and exists (select 1 from public.evidence_units eu where eu.id = pso.evidence_unit_id and eu.is_current = true)
  ) as execution_occurrences_with_evidence,
  (
    select count(*)::integer
    from public.entity_current_outcomes eco
    where eco.project_id = p.id
      and eco.outcome_type = 'execution_status'
      and eco.outcome_status = 'executed'
  ) as verified_execution_outcomes,
  (
    select count(*)::integer
    from public.project_context_elements pce
    where pce.project_id = p.id and pce.lifecycle_status = 'active'
  ) as context_elements,
  (
    select count(*)::integer
    from public.project_requirement_constraints prc
    where prc.project_id = p.id and prc.status = 'active'
  ) as requirement_constraints,
  coalesce(pos.observations_total, 0) as observations_total,
  coalesce(pos.observations_open, 0) as observations_open,
  coalesce(pos.observations_reconciled, 0) as observations_reconciled,
  coalesce(pos.observations_review_required, 0) as observations_review_required,
  coalesce(pos.observations_no_domain_object, 0) as observations_no_domain_object,
  case
    when (select count(*) from public.project_solution_instances psi where psi.project_id = p.id) = 0 then 0::numeric
    else round(
      100.0 * (
        select count(distinct pso.solution_instance_id)
        from public.project_solution_occurrences pso
        where pso.project_id = p.id
          and pso.lifecycle_status = 'active'
          and pso.evidence_unit_id is not null
          and exists (select 1 from public.evidence_units eu where eu.id = pso.evidence_unit_id and eu.is_current = true)
          and pso.legacy_memory_item_id is null
      ) / nullif((select count(*) from public.project_solution_instances psi where psi.project_id = p.id), 0),
      2
    )
  end as evidence_reconciliation_coverage_pct,
  (select migration_mode from public.project_domain_migration_state pdms where pdms.project_id = p.id) as migration_mode,
  (select domain_schema_version from public.project_domain_migration_state pdms where pdms.project_id = p.id) as domain_schema_version,
  (select last_completed_run_id from public.project_domain_migration_state pdms where pdms.project_id = p.id) as last_completed_run_id
from public.projects p
left join public.project_semantic_observation_status pos on pos.project_id = p.id;

-- --------------------------------------------------------------------------
-- 9. Atomic reconciliation writer.
-- --------------------------------------------------------------------------
create or replace function public.apply_project_domain_reconciliation_v2872a(
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
  v_project_entity_id uuid;
  v_domain_id uuid;
  v_entity_id uuid;
  v_context_sha text;
  v_observation_count integer := 0;
  v_solution_count integer := 0;
  v_occurrence_count integer := 0;
  v_outcome_count integer := 0;
  v_execution_outcome_count integer := 0;
  v_proposal_outcome_count integer := 0;
  v_context_count integer := 0;
  v_constraint_count integer := 0;
begin
  if not exists (select 1 from public.projects where id = p_project_id) then
    raise exception 'V28.7.2A: projeto % não existe', p_project_id;
  end if;
  if not exists (select 1 from public.intelligence_runs where id = p_run_id) then
    raise exception 'V28.7.2A: intelligence_run % não existe', p_run_id;
  end if;

  v_project_entity_id := nullif(p_bundle->>'project_entity_id','')::uuid;
  if v_project_entity_id is null then
    raise exception 'V28.7.2A: project_entity_id ausente';
  end if;

  -- Observations are upserted before domain mutations so every decision has lineage.
  for v_item in select value from jsonb_array_elements(coalesce(p_bundle->'observations','[]'::jsonb))
  loop
    insert into public.semantic_observations(
      id, project_id, source_asset_id, evidence_unit_id,
      observation_kind, observed_name, observed_type, observed_status,
      occurrence_phase, occurrence_role, attributes,
      source_authority_score, model_confidence, extraction_method,
      observation_hash, status, resolution_action,
      intelligence_run_id
    ) values (
      (v_item->>'id')::uuid,
      p_project_id,
      (v_item->>'source_asset_id')::uuid,
      (v_item->>'evidence_unit_id')::uuid,
      v_item->>'observation_kind',
      v_item->>'observed_name',
      nullif(v_item->>'observed_type',''),
      nullif(v_item->>'observed_status',''),
      coalesce(nullif(v_item->>'occurrence_phase',''),'reference'),
      coalesce(nullif(v_item->>'occurrence_role',''),'mention'),
      coalesce(v_item->'attributes','{}'::jsonb),
      nullif(v_item->>'source_authority_score','')::numeric,
      nullif(v_item->>'model_confidence','')::numeric,
      coalesce(nullif(v_item->>'extraction_method',''),'unknown'),
      v_item->>'observation_hash',
      'open',
      'none',
      p_run_id
    )
    on conflict (observation_hash)
    do update set
      observed_name = excluded.observed_name,
      observed_type = excluded.observed_type,
      observed_status = excluded.observed_status,
      occurrence_phase = excluded.occurrence_phase,
      occurrence_role = excluded.occurrence_role,
      attributes = coalesce(public.semantic_observations.attributes,'{}'::jsonb) || excluded.attributes,
      source_authority_score = greatest(coalesce(public.semantic_observations.source_authority_score,0), coalesce(excluded.source_authority_score,0)),
      model_confidence = greatest(coalesce(public.semantic_observations.model_confidence,0), coalesce(excluded.model_confidence,0)),
      intelligence_run_id = excluded.intelligence_run_id,
      updated_at = now();
    v_observation_count := v_observation_count + 1;
  end loop;

  -- Evidence-led solution creation only. Existing-domain attachment comes through occurrences below.
  for v_item in select value from jsonb_array_elements(coalesce(p_bundle->'solutions','[]'::jsonb))
  loop
    v_domain_id := (v_item->>'id')::uuid;
    v_entity_id := (v_item->>'entity_id')::uuid;

    insert into public.knowledge_entities(
      id, entity_type, canonical_name, normalized_name, entity_kind, scope_entity_id,
      domain_table, domain_id, attributes, status, confidence
    ) values (
      v_entity_id,
      case when coalesce(v_item->>'solution_kind','activation') = 'activation' then 'activation' else 'solution' end,
      coalesce(nullif(v_item->>'name',''),'Solução'),
      lower(coalesce(nullif(v_item->>'name',''),'solucao')),
      'project_instance',
      v_project_entity_id,
      'project_solution_instances',
      v_domain_id,
      jsonb_build_object('projection_only', true, 'normalized_by', 'V28.7.2A', 'origin', 'evidence_led_v2872a'),
      'active',
      nullif(v_item->>'confidence','')::numeric
    )
    on conflict (domain_table, domain_id)
      where domain_table is not null and domain_id is not null
    do update set
      scope_entity_id = excluded.scope_entity_id,
      attributes = coalesce(public.knowledge_entities.attributes,'{}'::jsonb) || excluded.attributes,
      confidence = greatest(coalesce(public.knowledge_entities.confidence,0), coalesce(excluded.confidence,0)),
      updated_at = now();

    insert into public.project_solution_instances(
      id, project_id, entity_id, identity_key, solution_kind, name, description,
      journey_stage, roles, proposal_status, execution_status,
      attributes, confidence, legacy_source_table, legacy_source_ids
    ) values (
      v_domain_id,
      p_project_id,
      v_entity_id,
      v_item->>'identity_key',
      coalesce(nullif(v_item->>'solution_kind',''),'activation'),
      coalesce(nullif(v_item->>'name',''),'Solução'),
      nullif(v_item->>'description',''),
      nullif(v_item->>'journey_stage',''),
      coalesce(array(select jsonb_array_elements_text(coalesce(v_item->'roles','[]'::jsonb))), '{}'::text[]),
      'unknown',
      'not_confirmed',
      coalesce(v_item->'attributes','{}'::jsonb),
      nullif(v_item->>'confidence','')::numeric,
      null,
      '{}'::uuid[]
    )
    on conflict (project_id, identity_key)
    do update set
      attributes = coalesce(public.project_solution_instances.attributes,'{}'::jsonb) || excluded.attributes,
      confidence = greatest(coalesce(public.project_solution_instances.confidence,0), coalesce(excluded.confidence,0)),
      updated_at = now();

    insert into public.domain_object_governance(
      entity_id, project_id, lifecycle_status, review_status,
      source_authority_score, model_confidence, field_authority,
      last_normalization_run_id, metadata
    ) values (
      v_entity_id, p_project_id, 'active', 'unreviewed',
      nullif(v_item->>'source_authority_score','')::numeric,
      nullif(v_item->>'confidence','')::numeric,
      jsonb_build_object(
        'name', coalesce(nullif(v_item->>'source_authority_score','')::numeric,0),
        'solution_kind', coalesce(nullif(v_item->>'source_authority_score','')::numeric,0)
      ),
      p_run_id,
      jsonb_build_object('normalized_by','V28.7.2A','origin','evidence_led_v2872a')
    )
    on conflict (entity_id) do update set
      source_authority_score = greatest(coalesce(public.domain_object_governance.source_authority_score,0), coalesce(excluded.source_authority_score,0)),
      model_confidence = greatest(coalesce(public.domain_object_governance.model_confidence,0), coalesce(excluded.model_confidence,0)),
      last_normalization_run_id = excluded.last_normalization_run_id,
      metadata = coalesce(public.domain_object_governance.metadata,'{}'::jsonb) || excluded.metadata,
      updated_at = now();

    v_solution_count := v_solution_count + 1;
  end loop;

  -- Occurrences: idempotent by deterministic id; no identity merge occurs here.
  for v_item in select value from jsonb_array_elements(coalesce(p_bundle->'occurrences','[]'::jsonb))
  loop
    insert into public.project_solution_occurrences(
      id, project_id, solution_instance_id,
      legacy_memory_item_id, source_asset_id, evidence_unit_id,
      occurrence_phase, occurrence_role,
      observed_name, observed_status, section_key, source_page, source_locator,
      confidence, lifecycle_status, normalization_run_id, attributes
    ) values (
      (v_item->>'id')::uuid,
      p_project_id,
      (v_item->>'solution_instance_id')::uuid,
      null,
      nullif(v_item->>'source_asset_id','')::uuid,
      nullif(v_item->>'evidence_unit_id','')::uuid,
      coalesce(nullif(v_item->>'occurrence_phase',''),'reference'),
      coalesce(nullif(v_item->>'occurrence_role',''),'reference'),
      nullif(v_item->>'observed_name',''),
      nullif(v_item->>'observed_status',''),
      nullif(v_item->>'section_key',''),
      nullif(v_item->>'source_page','')::integer,
      coalesce(v_item->'source_locator','{}'::jsonb),
      nullif(v_item->>'confidence','')::numeric,
      'active',
      p_run_id,
      coalesce(v_item->'attributes','{}'::jsonb)
    )
    on conflict (id) do update set
      confidence = greatest(coalesce(public.project_solution_occurrences.confidence,0), coalesce(excluded.confidence,0)),
      attributes = coalesce(public.project_solution_occurrences.attributes,'{}'::jsonb) || excluded.attributes,
      lifecycle_status = 'active',
      normalization_run_id = excluded.normalization_run_id,
      updated_at = now();
    v_occurrence_count := v_occurrence_count + 1;
  end loop;

  -- Domain evidence links for solution instances.
  for v_item in select value from jsonb_array_elements(coalesce(p_bundle->'evidence_links','[]'::jsonb))
  loop
    v_context_sha := encode(digest(coalesce(v_item->'context','{}'::jsonb)::text, 'sha256'), 'hex');
    insert into public.domain_object_evidence(
      project_id, object_entity_id, domain_table, domain_id, evidence_unit_id,
      link_role, context, context_sha256, binding_confidence, normalization_run_id
    ) values (
      p_project_id,
      (v_item->>'object_entity_id')::uuid,
      v_item->>'domain_table',
      (v_item->>'domain_id')::uuid,
      (v_item->>'evidence_unit_id')::uuid,
      coalesce(nullif(v_item->>'link_role',''),'occurrence'),
      coalesce(v_item->'context','{}'::jsonb),
      v_context_sha,
      nullif(v_item->>'binding_confidence','')::numeric,
      p_run_id
    )
    on conflict (object_entity_id, evidence_unit_id, link_role, context_sha256)
    do update set
      binding_confidence = greatest(coalesce(public.domain_object_evidence.binding_confidence,0), coalesce(excluded.binding_confidence,0)),
      normalization_run_id = excluded.normalization_run_id,
      updated_at = now();
  end loop;

  -- Evidence-led state outcomes are created only from observations with direct Evidence.
  for v_item in select value from jsonb_array_elements(coalesce(p_bundle->'outcomes','[]'::jsonb))
  loop
    insert into public.entity_outcomes(
      id, entity_id, project_id, outcome_type, outcome_status, outcome_at, reason,
      source_claim_id, source_evidence_id, source_observation_id,
      confidence, authority_score, is_human_confirmed,
      attributes, legacy_source_table, legacy_source_id, legacy_version_key, event_status
    ) values (
      (v_item->>'id')::uuid,
      (v_item->>'entity_id')::uuid,
      p_project_id,
      v_item->>'outcome_type',
      v_item->>'outcome_status',
      nullif(v_item->>'outcome_at','')::timestamptz,
      nullif(v_item->>'reason',''),
      null,
      nullif(v_item->>'source_evidence_id','')::uuid,
      nullif(v_item->>'source_observation_id','')::uuid,
      nullif(v_item->>'confidence','')::numeric,
      nullif(v_item->>'authority_score','')::numeric,
      false,
      coalesce(v_item->'attributes','{}'::jsonb),
      null,
      null,
      null,
      'active'
    )
    on conflict (id) do update set
      confidence = greatest(coalesce(public.entity_outcomes.confidence,0), coalesce(excluded.confidence,0)),
      authority_score = greatest(coalesce(public.entity_outcomes.authority_score,0), coalesce(excluded.authority_score,0)),
      attributes = coalesce(public.entity_outcomes.attributes,'{}'::jsonb) || excluded.attributes,
      event_status = 'active';
    v_outcome_count := v_outcome_count + 1;
    if v_item->>'outcome_type' = 'execution_status' then
      v_execution_outcome_count := v_execution_outcome_count + 1;
    elsif v_item->>'outcome_type' = 'proposal_status' then
      v_proposal_outcome_count := v_proposal_outcome_count + 1;
    end if;
  end loop;

  -- Project Solution Instance status columns remain compatibility projections.
  -- Recalculate execution status from the V28.7.1D provenance-gated current view
  -- after evidence-backed outcomes have been inserted.
  update public.project_solution_instances psi
  set proposal_status = coalesce((
        select eco.outcome_status
        from public.entity_current_outcomes eco
        where eco.entity_id = psi.entity_id
          and eco.outcome_type = 'proposal_status'
        limit 1
      ), 'unknown'),
      execution_status = coalesce((
        select eco.outcome_status
        from public.entity_current_outcomes eco
        where eco.entity_id = psi.entity_id
          and eco.outcome_type = 'execution_status'
        limit 1
      ), 'not_confirmed'),
      updated_at = now()
  where psi.project_id = p_project_id;

  -- Context elements + mirrors + provenance.
  for v_item in select value from jsonb_array_elements(coalesce(p_bundle->'context_elements','[]'::jsonb))
  loop
    v_domain_id := (v_item->>'id')::uuid;
    v_entity_id := (v_item->>'entity_id')::uuid;

    insert into public.knowledge_entities(
      id, entity_type, canonical_name, normalized_name, entity_kind, scope_entity_id,
      domain_table, domain_id, attributes, status, confidence
    ) values (
      v_entity_id, 'context_element', v_item->>'title', lower(v_item->>'title'),
      'project_instance', v_project_entity_id,
      'project_context_elements', v_domain_id,
      jsonb_build_object('projection_only',true,'normalized_by','V28.7.2A'),
      'active', nullif(v_item->>'confidence','')::numeric
    )
    on conflict (domain_table, domain_id)
      where domain_table is not null and domain_id is not null
    do update set
      canonical_name = excluded.canonical_name,
      normalized_name = excluded.normalized_name,
      confidence = greatest(coalesce(public.knowledge_entities.confidence,0), coalesce(excluded.confidence,0)),
      updated_at = now();

    insert into public.project_context_elements(
      id, project_id, entity_id, context_key, context_type, title, statement,
      scope, attributes, source_claim_id, source_evidence_id,
      confidence, authority_score, lifecycle_status, normalization_run_id
    ) values (
      v_domain_id, p_project_id, v_entity_id,
      v_item->>'context_key', v_item->>'context_type', v_item->>'title', v_item->>'statement',
      coalesce(v_item->'scope','{}'::jsonb), coalesce(v_item->'attributes','{}'::jsonb),
      nullif(v_item->>'source_claim_id','')::uuid,
      nullif(v_item->>'source_evidence_id','')::uuid,
      nullif(v_item->>'confidence','')::numeric,
      nullif(v_item->>'authority_score','')::numeric,
      'active', p_run_id
    )
    on conflict (project_id, context_key) do update set
      statement = case when excluded.authority_score >= coalesce(public.project_context_elements.authority_score,0)
                       then excluded.statement else public.project_context_elements.statement end,
      scope = coalesce(public.project_context_elements.scope,'{}'::jsonb) || excluded.scope,
      attributes = coalesce(public.project_context_elements.attributes,'{}'::jsonb) || excluded.attributes,
      source_evidence_id = coalesce(excluded.source_evidence_id, public.project_context_elements.source_evidence_id),
      confidence = greatest(coalesce(public.project_context_elements.confidence,0), coalesce(excluded.confidence,0)),
      authority_score = greatest(coalesce(public.project_context_elements.authority_score,0), coalesce(excluded.authority_score,0)),
      lifecycle_status = 'active',
      normalization_run_id = excluded.normalization_run_id,
      updated_at = now();

    insert into public.domain_object_governance(
      entity_id, project_id, lifecycle_status, review_status,
      source_authority_score, model_confidence, field_authority,
      last_normalization_run_id, metadata
    ) values (
      v_entity_id, p_project_id, 'active', 'unreviewed',
      nullif(v_item->>'authority_score','')::numeric,
      nullif(v_item->>'confidence','')::numeric,
      jsonb_build_object('statement',coalesce(nullif(v_item->>'authority_score','')::numeric,0)),
      p_run_id,
      jsonb_build_object('normalized_by','V28.7.2A','domain','context')
    )
    on conflict (entity_id) do update set
      source_authority_score = greatest(coalesce(public.domain_object_governance.source_authority_score,0), coalesce(excluded.source_authority_score,0)),
      model_confidence = greatest(coalesce(public.domain_object_governance.model_confidence,0), coalesce(excluded.model_confidence,0)),
      last_normalization_run_id = excluded.last_normalization_run_id,
      metadata = coalesce(public.domain_object_governance.metadata,'{}'::jsonb) || excluded.metadata,
      updated_at = now();

    if nullif(v_item->>'source_evidence_id','') is not null then
      v_context_sha := encode(digest(jsonb_build_object('context_key',v_item->>'context_key')::text, 'sha256'), 'hex');
      insert into public.domain_object_evidence(
        project_id, object_entity_id, domain_table, domain_id, evidence_unit_id,
        link_role, context, context_sha256, binding_confidence, normalization_run_id
      ) values (
        p_project_id, v_entity_id, 'project_context_elements', v_domain_id,
        (v_item->>'source_evidence_id')::uuid,
        'source', jsonb_build_object('context_key',v_item->>'context_key'), v_context_sha,
        nullif(v_item->>'confidence','')::numeric, p_run_id
      )
      on conflict (object_entity_id, evidence_unit_id, link_role, context_sha256)
      do update set
        binding_confidence = greatest(coalesce(public.domain_object_evidence.binding_confidence,0),coalesce(excluded.binding_confidence,0)),
        normalization_run_id = excluded.normalization_run_id,
        updated_at = now();
    end if;
    v_context_count := v_context_count + 1;
  end loop;

  -- Requirement constraints preserve numeric/range/scope semantics.
  for v_item in select value from jsonb_array_elements(coalesce(p_bundle->'requirement_constraints','[]'::jsonb))
  loop
    insert into public.project_requirement_constraints(
      id, project_id, requirement_id, constraint_type, operator,
      value_numeric, value_min, value_max, value_text, value_json,
      unit, currency, scope_type, scope_entity_id, scope_json,
      source_evidence_id, confidence, authority_score, status,
      constraint_hash, normalization_run_id
    ) values (
      (v_item->>'id')::uuid, p_project_id, (v_item->>'requirement_id')::uuid,
      v_item->>'constraint_type', v_item->>'operator',
      nullif(v_item->>'value_numeric','')::numeric,
      nullif(v_item->>'value_min','')::numeric,
      nullif(v_item->>'value_max','')::numeric,
      nullif(v_item->>'value_text',''),
      coalesce(v_item->'value_json','{}'::jsonb),
      nullif(v_item->>'unit',''), nullif(v_item->>'currency',''),
      coalesce(nullif(v_item->>'scope_type',''),'project'),
      nullif(v_item->>'scope_entity_id','')::uuid,
      coalesce(v_item->'scope_json','{}'::jsonb),
      (v_item->>'source_evidence_id')::uuid,
      nullif(v_item->>'confidence','')::numeric,
      nullif(v_item->>'authority_score','')::numeric,
      'active', v_item->>'constraint_hash', p_run_id
    )
    on conflict (constraint_hash) do update set
      confidence = greatest(coalesce(public.project_requirement_constraints.confidence,0), coalesce(excluded.confidence,0)),
      authority_score = greatest(coalesce(public.project_requirement_constraints.authority_score,0), coalesce(excluded.authority_score,0)),
      scope_json = coalesce(public.project_requirement_constraints.scope_json,'{}'::jsonb) || excluded.scope_json,
      status = 'active',
      normalization_run_id = excluded.normalization_run_id,
      updated_at = now();

    -- Constraint provenance is direct on project_requirement_constraints.source_evidence_id.
    -- It deliberately reuses the parent Requirement entity only as parent linkage, not as a false mirror for the child constraint.
    v_constraint_count := v_constraint_count + 1;
  end loop;

  -- Apply observation resolutions only after all referenced domain objects exist.
  for v_resolution in select value from jsonb_array_elements(coalesce(p_bundle->'observation_resolutions','[]'::jsonb))
  loop
    update public.semantic_observations
    set status = coalesce(nullif(v_resolution->>'status',''),'open'),
        resolution_action = coalesce(nullif(v_resolution->>'resolution_action',''),'none'),
        resolved_entity_id = nullif(v_resolution->>'resolved_entity_id','')::uuid,
        resolved_domain_table = nullif(v_resolution->>'resolved_domain_table',''),
        resolved_domain_id = nullif(v_resolution->>'resolved_domain_id','')::uuid,
        resolution_detail = coalesce(v_resolution->'resolution_detail','{}'::jsonb),
        resolution_run_id = p_run_id,
        updated_at = now()
    where id = (v_resolution->>'id')::uuid;
  end loop;

  -- Keep shadow mode. Schema version advances, cutover does not.
  insert into public.project_domain_migration_state(
    project_id, migration_mode, domain_schema_version, last_completed_run_id
  ) values (
    p_project_id, 'legacy_shadow', '28.7.2a', p_run_id
  )
  on conflict (project_id) do update set
    migration_mode = 'legacy_shadow',
    domain_schema_version = excluded.domain_schema_version,
    last_completed_run_id = excluded.last_completed_run_id,
    updated_at = now();

  update public.intelligence_runs
  set status = 'completed',
      completed_at = now(),
      output_signature = encode(digest(jsonb_build_object(
        'observations',v_observation_count,
        'solutions',v_solution_count,
        'occurrences',v_occurrence_count,
        'outcomes',v_outcome_count,
        'execution_outcomes',v_execution_outcome_count,
        'proposal_outcomes',v_proposal_outcome_count,
        'context',v_context_count,
        'constraints',v_constraint_count
      )::text,'sha256'),'hex'),
      metadata = coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
        'observations',v_observation_count,
        'solutions_created_or_refreshed',v_solution_count,
        'occurrences',v_occurrence_count,
        'outcomes',v_outcome_count,
        'execution_outcomes',v_execution_outcome_count,
        'proposal_outcomes',v_proposal_outcome_count,
        'context_elements',v_context_count,
        'requirement_constraints',v_constraint_count,
        'migration_mode','legacy_shadow'
      )
  where id = p_run_id;

  return jsonb_build_object(
    'status','completed',
    'project_id',p_project_id,
    'run_id',p_run_id,
    'observations',v_observation_count,
    'solutions',v_solution_count,
    'occurrences',v_occurrence_count,
    'outcomes',v_outcome_count,
    'execution_outcomes',v_execution_outcome_count,
    'proposal_outcomes',v_proposal_outcome_count,
    'context_elements',v_context_count,
    'requirement_constraints',v_constraint_count,
    'migration_mode','legacy_shadow'
  );
end;
$$;

comment on table public.semantic_observations is
  'V28.7.2A — observações evidence-backed antes de qualquer compromisso de identidade de domínio.';
comment on table public.project_context_elements is
  'V28.7.2A — contexto de projeto/briefing de primeira classe; distinto de requirements e strategy.';
comment on table public.project_requirement_constraints is
  'V28.7.2A — constraints quantitativas e scoped; ranges permanecem ranges.';
comment on function public.apply_project_domain_reconciliation_v2872a(uuid,uuid,jsonb) is
  'V28.7.2A — writer transacional de Semantic Observation -> Reconciliation -> Domain; nunca promove domain_primary.';

-- --------------------------------------------------------------------------
-- 10. Private server-side security, same Foundation model.
-- --------------------------------------------------------------------------
do $$
declare
  t text;
begin
  foreach t in array array['semantic_observations','project_context_elements','project_requirement_constraints']
  loop
    execute format('alter table public.%I enable row level security', t);
    execute format('revoke all on public.%I from anon, authenticated', t);
    execute format('grant select, insert, update on public.%I to service_role', t);
    execute format('grant select, insert, update, delete on public.%I to postgres', t);
  end loop;
end $$;

revoke all on function public.apply_project_domain_reconciliation_v2872a(uuid,uuid,jsonb)
  from public, anon, authenticated;
grant execute on function public.apply_project_domain_reconciliation_v2872a(uuid,uuid,jsonb)
  to service_role, postgres;

-- --------------------------------------------------------------------------
-- 11. Install self-check.
-- --------------------------------------------------------------------------
do $$
begin
  if to_regclass('public.semantic_observations') is null then
    raise exception 'V28.7.2A install check failed: semantic_observations missing';
  end if;
  if to_regclass('public.project_context_elements') is null then
    raise exception 'V28.7.2A install check failed: project_context_elements missing';
  end if;
  if to_regclass('public.project_requirement_constraints') is null then
    raise exception 'V28.7.2A install check failed: project_requirement_constraints missing';
  end if;
  if to_regclass('public.project_domain_reconciliation_status') is null then
    raise exception 'V28.7.2A install check failed: reconciliation status view missing';
  end if;
  if to_regprocedure('public.apply_project_domain_reconciliation_v2872a(uuid,uuid,jsonb)') is null then
    raise exception 'V28.7.2A install check failed: reconciliation RPC missing';
  end if;
  if not exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'entity_outcomes' and column_name = 'source_observation_id'
  ) then
    raise exception 'V28.7.2A install check failed: entity_outcomes.source_observation_id missing';
  end if;
  if not exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'project_domain_reconciliation_status'
      and column_name = 'evidence_reconciliation_coverage_pct'
  ) then
    raise exception 'V28.7.2A install check failed: reconciliation coverage field missing';
  end if;
end $$;

notify pgrst, 'reload schema';
commit;
