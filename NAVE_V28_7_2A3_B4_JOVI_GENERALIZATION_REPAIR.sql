-- NAVE by VOE · V28.7.2A3+B4 — JOVI Semantic Precision Repair
-- ONE-TIME REPAIR. Target is resolved by the two Golden source filenames.
-- Preserves history; no DELETE; no Graph V28.6; no domain_primary.

begin;

do $$
begin
  if to_regclass('public.project_strategy_elements') is null
     or to_regclass('public.project_experience_architectures') is null
     or to_regclass('public.project_journey_moments') is null
     or to_regclass('public.semantic_observations') is null
     or to_regclass('public.domain_object_governance') is null
     or to_regclass('public.knowledge_entities') is null
     or to_regclass('public.knowledge_relations') is null then
    raise exception 'V28.7.2A3+B4 prerequisite missing';
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
    raise exception 'V28.7.2A3+B4: Golden JOVI project not found by sources';
  end if;
end $$;

create temporary table nave_v2872_bad_strategy as
select distinct
  pse.id as domain_id,
  pse.entity_id,
  pse.source_observation_id,
  pse.title,
  pse.strategy_type
from public.project_strategy_elements pse
join nave_v2872_jovi_target t on t.project_id=pse.project_id
join public.semantic_observations so on so.id=pse.source_observation_id
join public.evidence_units eu on eu.id=pse.source_evidence_id
left join public.evidence_units parent_eu
  on parent_eu.id = case
      when coalesce(so.attributes->>'heading_evidence_id','') ~* '^[0-9a-f-]{36}$'
      then (so.attributes->>'heading_evidence_id')::uuid
      else null
    end
where pse.lifecycle_status='active'
  and (
    (
      pse.strategy_type='territory'
      and lower(trim(pse.title)) in ('highlights','insight','insights')
    )
    or (
      coalesce(so.attributes->>'adjacent_explicit_heading','false')='true'
      and (
        right(trim(coalesce(eu.content_text,'')),1)=':'
        or (
          coalesce(parent_eu.content_text,'') ~* '(alinhamento estrategico|strategic alignment)'
          and coalesce(parent_eu.content_text,'') ~* '(publico.?alvo|target audience)'
        )
      )
    )
  );

create temporary table nave_v2872_bad_experience as
select distinct
  pea.id as domain_id,
  pea.entity_id,
  pea.source_observation_id,
  pea.name
from public.project_experience_architectures pea
join nave_v2872_jovi_target t on t.project_id=pea.project_id
join public.evidence_units eu on eu.id=pea.source_evidence_id
where pea.lifecycle_status='active'
  and lower(trim(pea.name)) in ('journey','jornada')
  and coalesce(eu.content_text,'') !~* '(event[[:space:]]+journey|experience[[:space:]]+journey|jornada[[:space:]]+do[[:space:]]+evento|pre[[:space:]-]+event.*post[[:space:]-]+event)';

create temporary table nave_v2872_bad_journey as
select distinct
  pjm.id as domain_id,
  pjm.entity_id,
  pjm.source_observation_id,
  pjm.title,
  pjm.moment_type
from public.project_journey_moments pjm
where pjm.lifecycle_status='active'
  and pjm.architecture_id in (select domain_id from nave_v2872_bad_experience);

update public.project_strategy_elements x
set lifecycle_status='invalidated',
    attributes=coalesce(x.attributes,'{}'::jsonb)||jsonb_build_object(
      'invalidated_by','V28.7.2B4',
      'invalidation_reason','jovi_generalization_precision_repair',
      'invalidated_at',now()
    ),
    updated_at=now()
where x.id in (select domain_id from nave_v2872_bad_strategy);

update public.project_experience_architectures x
set lifecycle_status='invalidated',
    attributes=coalesce(x.attributes,'{}'::jsonb)||jsonb_build_object(
      'invalidated_by','V28.7.2B4',
      'invalidation_reason','generic_journey_copy_is_not_architecture',
      'invalidated_at',now()
    ),
    updated_at=now()
where x.id in (select domain_id from nave_v2872_bad_experience);

update public.project_journey_moments x
set lifecycle_status='invalidated',
    attributes=coalesce(x.attributes,'{}'::jsonb)||jsonb_build_object(
      'invalidated_by','V28.7.2B4',
      'invalidation_reason','parent_architecture_invalidated',
      'invalidated_at',now()
    ),
    updated_at=now()
where x.id in (select domain_id from nave_v2872_bad_journey);

create temporary table nave_v2872_bad_entities as
select entity_id,source_observation_id from nave_v2872_bad_strategy
union
select entity_id,source_observation_id from nave_v2872_bad_experience
union
select entity_id,source_observation_id from nave_v2872_bad_journey;

update public.domain_object_governance g
set lifecycle_status='invalidated',
    lifecycle_reason='V28.7.2B4: semantic precision repair',
    lifecycle_at=now(),
    metadata=coalesce(g.metadata,'{}'::jsonb)||jsonb_build_object(
      'invalidated_by','V28.7.2B4','repair_kind','jovi_generalization_precision'
    ),
    updated_at=now()
where g.entity_id in (select entity_id from nave_v2872_bad_entities);

update public.knowledge_entities ke
set status='inactive',
    valid_to=coalesce(ke.valid_to,now()),
    attributes=coalesce(ke.attributes,'{}'::jsonb)||jsonb_build_object(
      'invalidated_by','V28.7.2B4','invalidation_reason','semantic_precision_repair'
    ),
    updated_at=now()
where ke.id in (select entity_id from nave_v2872_bad_entities);

update public.semantic_observations so
set status='superseded',
    resolution_action='none',
    resolved_entity_id=null,
    resolved_domain_table=null,
    resolved_domain_id=null,
    resolution_detail=coalesce(so.resolution_detail,'{}'::jsonb)||jsonb_build_object(
      'superseded_by','V28.7.2B4','reason','semantic_precision_repair','repaired_at',now()
    ),
    updated_at=now()
where so.id in (select source_observation_id from nave_v2872_bad_entities where source_observation_id is not null);

update public.knowledge_relations kr
set status='superseded',
    valid_to=coalesce(kr.valid_to,now()),
    attributes=coalesce(kr.attributes,'{}'::jsonb)||jsonb_build_object(
      'superseded_by','V28.7.2B4','reason','relation_touched_invalidated_core_entity'
    ),
    updated_at=now()
where kr.status='active'
  and (
    kr.source_entity_id in (select entity_id from nave_v2872_bad_entities)
    or kr.target_entity_id in (select entity_id from nave_v2872_bad_entities)
  );

commit;

select
  (select project_id from nave_v2872_jovi_target limit 1) as project_id,
  (select count(*)::integer from nave_v2872_bad_strategy) as invalidated_strategy,
  (select count(*)::integer from nave_v2872_bad_experience) as invalidated_experience_architectures,
  (select count(*)::integer from nave_v2872_bad_journey) as invalidated_journey_moments,
  coalesce((select jsonb_agg(jsonb_build_object('type',strategy_type,'title',title) order by title) from nave_v2872_bad_strategy),'[]'::jsonb) as strategy_history,
  coalesce((select jsonb_agg(jsonb_build_object('name',name) order by name) from nave_v2872_bad_experience),'[]'::jsonb) as experience_history,
  coalesce((select jsonb_agg(jsonb_build_object('type',moment_type,'title',title) order by title) from nave_v2872_bad_journey),'[]'::jsonb) as journey_history;
