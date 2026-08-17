-- NAVE by VOE · V28.7.2A4 + B5
-- Cross-language Identity Anchor Repair + residual Strategy cleanup
-- ONE-TIME REPAIR for Golden JOVI. No DELETE. Preserves historical auditability.

begin;

do $$
begin
  if to_regclass('public.semantic_observations') is null
     or to_regclass('public.project_solution_instances') is null
     or to_regclass('public.project_solution_occurrences') is null
     or to_regclass('public.entity_outcomes') is null
     or to_regclass('public.project_strategy_elements') is null then
    raise exception 'V28.7.2A4+B5 prerequisite missing';
  end if;
end $$;

create temporary table nave_v2872_jovi_target as
with candidates as (
  select pf.project_id,
         count(*) filter(where lower(coalesce(pf.file_name,'')) like '%lancamento_jovi_x300%') as proposal_matches,
         count(*) filter(where lower(coalesce(pf.file_name,'')) like '%briefing_jovi_x300%') as briefing_matches
  from public.project_files pf
  where lower(coalesce(pf.file_name,'')) like '%lancamento_jovi_x300%'
     or lower(coalesce(pf.file_name,'')) like '%briefing_jovi_x300%'
  group by pf.project_id
)
select project_id
from candidates
where proposal_matches>0 and briefing_matches>0
order by project_id
limit 1;

do $$
begin
  if not exists(select 1 from nave_v2872_jovi_target) then
    raise exception 'V28.7.2A4+B5: Golden JOVI project not found by sources';
  end if;
end $$;

-- A3 exposed a resolver bug: English "activation" was treated as a unique identity
-- anchor. This caused YouTube/Instagram/TikTok observations to attach to KWAI activation.
create temporary table nave_v2872_bad_platform_observations as
select
  so.id as observation_id,
  so.observed_name,
  so.resolved_domain_id as solution_id,
  so.resolved_entity_id as solution_entity_id,
  psi.name as solution_name
from public.semantic_observations so
join nave_v2872_jovi_target t on t.project_id=so.project_id
join public.project_solution_instances psi
  on psi.id=so.resolved_domain_id
 and psi.project_id=so.project_id
where so.status='reconciled'
  and so.resolved_domain_table='project_solution_instances'
  and coalesce(psi.attributes->>'origin','')='evidence_led_v2872a'
  and lower(trim(coalesce(so.observed_name,''))) ~ ' activation$'
  and lower(trim(coalesce(psi.name,''))) ~ ' activation$'
  and regexp_replace(lower(trim(so.observed_name)), '\s+activation\s*$', '') <>
      regexp_replace(lower(trim(psi.name)), '\s+activation\s*$', '');

create temporary table nave_v2872_bad_platform_occurrences as
select pso.id, pso.solution_instance_id, pso.evidence_unit_id, pso.observed_name,
       pso.attributes->>'semantic_observation_id' as semantic_observation_id
from public.project_solution_occurrences pso
join nave_v2872_jovi_target t on t.project_id=pso.project_id
where pso.lifecycle_status='active'
  and coalesce(pso.attributes->>'semantic_observation_id','') in (
    select observation_id::text from nave_v2872_bad_platform_observations
  );

create temporary table nave_v2872_bad_platform_outcomes as
select eo.id, eo.entity_id, eo.source_observation_id, eo.reason
from public.entity_outcomes eo
join nave_v2872_jovi_target t on t.project_id=eo.project_id
where eo.event_status='active'
  and eo.source_observation_id in (
    select observation_id from nave_v2872_bad_platform_observations
  );

update public.project_solution_occurrences pso
set lifecycle_status='invalidated',
    attributes=coalesce(pso.attributes,'{}'::jsonb)||jsonb_build_object(
      'invalidated_by','V28.7.2A4',
      'invalidation_reason','cross_language_generic_identity_anchor',
      'invalidated_at',now()
    ),
    updated_at=now()
where pso.id in (select id from nave_v2872_bad_platform_occurrences);

update public.entity_outcomes eo
set event_status='superseded',
    invalidation_reason='V28.7.2A4: cross-language generic identity anchor attached proposal truth to wrong solution',
    attributes=coalesce(eo.attributes,'{}'::jsonb)||jsonb_build_object(
      'superseded_by_repair','V28.7.2A4',
      'repair_reason','cross_language_generic_identity_anchor'
    )
where eo.id in (select id from nave_v2872_bad_platform_outcomes);

-- Keep the same Semantic Observation id, but reopen the wrong resolution so the next
-- deterministic reconciliation can attach/create the correct identity.
update public.semantic_observations so
set status='open',
    resolution_action='none',
    resolved_entity_id=null,
    resolved_domain_table=null,
    resolved_domain_id=null,
    resolution_detail=coalesce(so.resolution_detail,'{}'::jsonb)||jsonb_build_object(
      'reopened_by','V28.7.2A4',
      'reason','cross_language_generic_identity_anchor',
      'reopened_at',now()
    ),
    updated_at=now()
where so.id in (select observation_id from nave_v2872_bad_platform_observations);

-- Historical object-level evidence links are retained, but the wrong binding is
-- downgraded from occurrence support to context-only with zero confidence.
update public.domain_object_evidence doe
set link_role='context_only',
    binding_confidence=0,
    updated_at=now()
where doe.project_id=(select project_id from nave_v2872_jovi_target limit 1)
  and doe.link_role='occurrence'
  and coalesce(doe.context->>'semantic_observation_id','') in (
    select observation_id::text from nave_v2872_bad_platform_observations
  );

-- B4 runtime already stops audience content from being emitted as Strategy, but the
-- earlier persisted "Frequentadores..." object survived because the previous repair
-- did not select it. Invalidate the stale historical object now.
create temporary table nave_v2872_bad_strategy as
select pse.id as domain_id,pse.entity_id,pse.source_observation_id,pse.title,pse.strategy_type
from public.project_strategy_elements pse
join nave_v2872_jovi_target t on t.project_id=pse.project_id
where pse.lifecycle_status='active'
  and lower(trim(pse.title)) like 'frequentadores de festivais%';

update public.project_strategy_elements pse
set lifecycle_status='invalidated',
    attributes=coalesce(pse.attributes,'{}'::jsonb)||jsonb_build_object(
      'invalidated_by','V28.7.2B5',
      'invalidation_reason','audience_context_is_not_strategic_direction',
      'invalidated_at',now()
    ),
    updated_at=now()
where pse.id in (select domain_id from nave_v2872_bad_strategy);

update public.domain_object_governance g
set lifecycle_status='invalidated',
    lifecycle_reason='V28.7.2B5: audience context is not strategic direction',
    lifecycle_at=now(),
    metadata=coalesce(g.metadata,'{}'::jsonb)||jsonb_build_object(
      'invalidated_by','V28.7.2B5',
      'repair_kind','strategy_scope_precision'
    ),
    updated_at=now()
where g.entity_id in (select entity_id from nave_v2872_bad_strategy);

update public.knowledge_entities ke
set status='inactive',
    valid_to=coalesce(ke.valid_to,now()),
    attributes=coalesce(ke.attributes,'{}'::jsonb)||jsonb_build_object(
      'invalidated_by','V28.7.2B5',
      'invalidation_reason','audience_context_is_not_strategic_direction'
    ),
    updated_at=now()
where ke.id in (select entity_id from nave_v2872_bad_strategy);

update public.semantic_observations so
set status='superseded',
    resolution_action='none',
    resolved_entity_id=null,
    resolved_domain_table=null,
    resolved_domain_id=null,
    resolution_detail=coalesce(so.resolution_detail,'{}'::jsonb)||jsonb_build_object(
      'superseded_by','V28.7.2B5',
      'reason','audience_context_is_not_strategic_direction',
      'repaired_at',now()
    ),
    updated_at=now()
where so.id in (
  select source_observation_id from nave_v2872_bad_strategy
  where source_observation_id is not null
);

update public.knowledge_relations kr
set status='superseded',
    valid_to=coalesce(kr.valid_to,now()),
    attributes=coalesce(kr.attributes,'{}'::jsonb)||jsonb_build_object(
      'superseded_by','V28.7.2B5',
      'reason','relation_touched_invalidated_strategy_entity'
    ),
    updated_at=now()
where kr.status='active'
  and (
    kr.source_entity_id in (select entity_id from nave_v2872_bad_strategy)
    or kr.target_entity_id in (select entity_id from nave_v2872_bad_strategy)
  );

commit;

select
  (select project_id from nave_v2872_jovi_target limit 1) as project_id,
  (select count(*)::integer from nave_v2872_bad_platform_observations) as reopened_cross_platform_observations,
  (select count(*)::integer from nave_v2872_bad_platform_occurrences) as invalidated_cross_platform_occurrences,
  (select count(*)::integer from nave_v2872_bad_platform_outcomes) as superseded_cross_platform_outcomes,
  (select count(*)::integer from nave_v2872_bad_strategy) as invalidated_strategy,
  coalesce((
    select jsonb_agg(jsonb_build_object(
      'observed_name',observed_name,
      'wrong_solution_name',solution_name,
      'observation_id',observation_id
    ) order by observed_name)
    from nave_v2872_bad_platform_observations
  ),'[]'::jsonb) as platform_resolution_history,
  coalesce((
    select jsonb_agg(jsonb_build_object(
      'type',strategy_type,'title',title
    ) order by title)
    from nave_v2872_bad_strategy
  ),'[]'::jsonb) as strategy_history;
