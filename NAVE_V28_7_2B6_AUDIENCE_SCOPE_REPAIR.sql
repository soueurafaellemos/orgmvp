-- NAVE by VOE · V28.7.2B6 — Audience Scope Finalizer
-- ONE-TIME REPAIR for stale Strategy pollution in Golden JOVI.
-- Runtime fix is generic; this repair only invalidates already-persisted stale history.
-- No DELETE. Preserves Evidence and audit trail.

begin;

do $$
begin
  if to_regclass('public.project_strategy_elements') is null
     or to_regclass('public.semantic_observations') is null
     or to_regclass('public.domain_object_governance') is null
     or to_regclass('public.knowledge_entities') is null then
    raise exception 'V28.7.2B6 prerequisite missing';
  end if;
end $$;

create temporary table nave_v2872b6_target as
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
  if not exists(select 1 from nave_v2872b6_target) then
    raise exception 'V28.7.2B6: Golden JOVI project not found by source pair';
  end if;
end $$;

create temporary table nave_v2872b6_bad_strategy as
select
  pse.id as domain_id,
  pse.entity_id,
  pse.source_observation_id,
  pse.title,
  pse.strategy_type
from public.project_strategy_elements pse
join nave_v2872b6_target t on t.project_id=pse.project_id
left join public.semantic_observations so on so.id=pse.source_observation_id
left join public.evidence_units heading_eu
  on heading_eu.id = case
    when coalesce(so.attributes->>'heading_evidence_id','') ~* '^[0-9a-f-]{36}$'
    then (so.attributes->>'heading_evidence_id')::uuid
    else null
  end
where pse.lifecycle_status='active'
  and pse.strategy_type='strategic_direction'
  and (
    -- Generic path: child signal emitted from a strategic heading whose own
    -- scope explicitly points to audience / target audience.
    (
      coalesce(so.attributes->>'adjacent_explicit_heading','false')='true'
      and lower(
        translate(
          coalesce(heading_eu.content_text,''),
          'ÁÀÃÂÉÊÍÓÔÕÚÇáàãâéêíóôõúç',
          'AAAAEEIOOOUCaaaaeeiooouc'
        )
      ) ~ '(publico[- ]?alvo|target audience|audience profile|perfil de publico)'
    )
    -- Historical fallback for the already-known stale JOVI object created
    -- before the generic boundary existed.
    or lower(trim(pse.title)) like 'frequentadores de festivais%'
  );

update public.project_strategy_elements pse
set lifecycle_status='invalidated',
    attributes=coalesce(pse.attributes,'{}'::jsonb)||jsonb_build_object(
      'invalidated_by','V28.7.2B6',
      'invalidation_reason','audience_child_is_not_strategic_direction',
      'invalidated_at',now()
    ),
    updated_at=now()
where pse.id in (select domain_id from nave_v2872b6_bad_strategy);

update public.domain_object_governance g
set lifecycle_status='invalidated',
    lifecycle_reason='V28.7.2B6: audience child is not a strategic direction',
    lifecycle_at=now(),
    metadata=coalesce(g.metadata,'{}'::jsonb)||jsonb_build_object(
      'invalidated_by','V28.7.2B6',
      'repair_kind','strategy_audience_scope'
    ),
    updated_at=now()
where g.entity_id in (select entity_id from nave_v2872b6_bad_strategy);

update public.knowledge_entities ke
set status='inactive',
    valid_to=coalesce(ke.valid_to,now()),
    attributes=coalesce(ke.attributes,'{}'::jsonb)||jsonb_build_object(
      'invalidated_by','V28.7.2B6',
      'invalidation_reason','audience_child_is_not_strategic_direction'
    ),
    updated_at=now()
where ke.id in (select entity_id from nave_v2872b6_bad_strategy);

update public.semantic_observations so
set status='superseded',
    resolution_action='none',
    resolved_entity_id=null,
    resolved_domain_table=null,
    resolved_domain_id=null,
    resolution_detail=coalesce(so.resolution_detail,'{}'::jsonb)||jsonb_build_object(
      'superseded_by','V28.7.2B6',
      'reason','audience_child_is_not_strategic_direction',
      'repaired_at',now()
    ),
    updated_at=now()
where so.id in (
  select source_observation_id
  from nave_v2872b6_bad_strategy
  where source_observation_id is not null
);

update public.knowledge_relations kr
set status='superseded',
    valid_to=coalesce(kr.valid_to,now()),
    attributes=coalesce(kr.attributes,'{}'::jsonb)||jsonb_build_object(
      'superseded_by','V28.7.2B6',
      'reason','relation_touched_invalidated_audience_strategy'
    ),
    updated_at=now()
where kr.status='active'
  and (
    kr.source_entity_id in (select entity_id from nave_v2872b6_bad_strategy)
    or kr.target_entity_id in (select entity_id from nave_v2872b6_bad_strategy)
  );

commit;

select
  (select project_id from nave_v2872b6_target limit 1) as project_id,
  count(*)::integer as invalidated_strategy_rows,
  coalesce(jsonb_agg(
    jsonb_build_object(
      'strategy_type',strategy_type,
      'title',title,
      'domain_id',domain_id,
      'entity_id',entity_id
    )
    order by lower(title)
  ),'[]'::jsonb) as invalidated_rows
from nave_v2872b6_bad_strategy;
