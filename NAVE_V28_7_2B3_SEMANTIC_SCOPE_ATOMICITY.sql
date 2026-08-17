-- NAVE by VOE · V28.7.2B3 — Semantic Scope & Atomicity
-- VIEW-ONLY HOTFIX. Não altera objetos de domínio, Evidence, Truth Gate de outcomes,
-- Solutions, Finance ou Graph V28.6.

begin;

do $$
begin
  if to_regclass('public.semantic_observations') is null
     or to_regclass('public.project_core_semantic_truth_status') is null
     or to_regclass('public.project_strategy_elements') is null then
    raise exception 'V28.7.2B3 prerequisite missing: V28.7.2A/B not installed';
  end if;
end $$;

-- --------------------------------------------------------------------------
-- 1. V28.7.2A debugger must remain scoped to the Reconciliation Kernel.
--    Strategy/Creative/Experience/Journey observations share the same staging
--    table, but must not inflate A-level observation counters.
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
  and (
    so.domain_hint is null
    or so.domain_hint not in ('strategy','creative','experience','journey')
  )
  and exists (
    select 1 from public.evidence_units eu
    where eu.id = so.evidence_unit_id and eu.is_current = true
  )
group by p.id;

-- --------------------------------------------------------------------------
-- 2. Core B status is a CURRENT-state dashboard.
--    Invalidated historical objects remain visible in the truth-status view,
--    but they must not be counted as current "Unsupported".
-- --------------------------------------------------------------------------
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
  (select count(*)::integer from public.project_core_semantic_truth_status t where t.project_id=p.id and t.lifecycle_status='active' and t.truth_state='verified_explicit') as verified_explicit,
  (select count(*)::integer from public.project_core_semantic_truth_status t where t.project_id=p.id and t.lifecycle_status='active' and t.truth_state='verified_synthesis') as verified_synthesis,
  (select count(*)::integer from public.project_core_semantic_truth_status t where t.project_id=p.id and t.lifecycle_status='active' and t.truth_state='human_confirmed') as human_confirmed,
  (select count(*)::integer from public.project_core_semantic_truth_status t where t.project_id=p.id and t.lifecycle_status='active' and t.truth_state='review_required') as review_required,
  (select count(*)::integer from public.project_core_semantic_truth_status t where t.project_id=p.id and t.lifecycle_status='active' and t.truth_state='unsupported') as unsupported,
  (
    select count(*)::integer
    from public.semantic_observations so
    where so.project_id=p.id
      and so.domain_hint in ('strategy','creative','experience','journey')
      and so.status <> 'superseded'
  ) as semantic_observations,
  (
    select count(*)::integer
    from public.semantic_observations so
    where so.project_id=p.id
      and so.domain_hint in ('strategy','creative','experience','journey')
      and so.status='open'
  ) as semantic_observations_open,
  (
    select count(*)::integer
    from public.knowledge_relations kr
    join public.knowledge_entities pe
      on pe.id=kr.scope_entity_id and pe.domain_table='projects' and pe.domain_id=p.id
    where kr.status='active'
      and kr.relation_kind='fact'
      and coalesce(kr.attributes->>'normalized_by','')='V28.7.2B'
  ) as fact_relations,
  (
    select count(*)::integer
    from public.knowledge_relations kr
    join public.knowledge_entities pe
      on pe.id=kr.scope_entity_id and pe.domain_table='projects' and pe.domain_id=p.id
    where kr.status='active'
      and kr.relation_kind='inference'
      and coalesce(kr.attributes->>'normalized_by','')='V28.7.2B'
  ) as inference_relations,
  (select migration_mode from public.project_domain_migration_state pdms where pdms.project_id=p.id) as migration_mode,
  (select domain_schema_version from public.project_domain_migration_state pdms where pdms.project_id=p.id) as domain_schema_version,
  (
    select ir.id
    from public.intelligence_runs ir
    join public.knowledge_entities pe
      on pe.id=ir.scope_entity_id and pe.domain_table='projects' and pe.domain_id=p.id
    where ir.analyzer_type='project_core_semantic_domains' and ir.status='completed'
    order by ir.created_at desc
    limit 1
  ) as last_completed_run_id
from public.projects p;

revoke all on public.project_semantic_observation_status from anon, authenticated;
revoke all on public.project_core_semantic_status from anon, authenticated;
grant select on public.project_semantic_observation_status to service_role, postgres;
grant select on public.project_core_semantic_status to service_role, postgres;

comment on view public.project_semantic_observation_status is
  'V28.7.2A reconciliation observation status only; V28.7.2B Core Semantic observations are excluded from A counters.';
comment on view public.project_core_semantic_status is
  'Current-state V28.7.2B dashboard. Invalidated historical Core Semantic objects do not count as current unsupported truth.';

commit;

select
  'V28.7.2B3 installed'::text as status,
  to_regclass('public.project_semantic_observation_status') is not null as reconciliation_scope_view_ok,
  to_regclass('public.project_core_semantic_status') is not null as core_status_view_ok;
