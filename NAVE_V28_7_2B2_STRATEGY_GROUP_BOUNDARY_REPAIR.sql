-- NAVE by VOE · V28.7.2B2 — Strategy Group Boundary & Precision Repair
-- ONE-TIME REPAIR. Preserva histórico; não apaga Evidence nem objetos.
-- Corrige apenas Strategy materializada por vazamento de grupo explícito
-- (ex.: um bloco "Pilares:" que atravessou um novo heading/recursos).
--
-- Ordem recomendada:
-- 1) subir o Python B2 e rebootar;
-- 2) executar ESTE SQL uma vez;
-- 3) executar novamente "Reconciliar Core Semantic Domains · V28.7.2B".
--
-- Não altera Truth Gate, Solutions, Finance, Graph V28.6 ou migration_mode.

begin;

do $$
begin
  if to_regclass('public.project_strategy_elements') is null
     or to_regclass('public.semantic_observations') is null
     or to_regclass('public.evidence_units') is null
     or to_regclass('public.knowledge_entities') is null
     or to_regclass('public.domain_object_governance') is null
     or to_regclass('public.knowledge_relations') is null then
    raise exception 'V28.7.2B2 prerequisite missing: V28.7.2B / Foundation / Domain Integrity';
  end if;
end $$;

drop table if exists pg_temp.nave_v2872b2_invalid_strategy;

create temporary table nave_v2872b2_invalid_strategy as
select distinct
  pse.id as strategy_id,
  pse.project_id,
  pse.entity_id,
  pse.title,
  pse.strategy_type,
  pse.source_observation_id,
  pse.source_evidence_id,
  eu.content_text as evidence_text
from public.project_strategy_elements pse
join public.semantic_observations so
  on so.id = pse.source_observation_id
join public.evidence_units eu
  on eu.id = pse.source_evidence_id
where pse.lifecycle_status = 'active'
  and so.domain_hint = 'strategy'
  and coalesce(so.attributes->>'adjacent_explicit_group_heading','false') = 'true'
  and (
    coalesce(eu.content_text,'') ~* '(https?://|www\.)'
    or (
      right(trim(coalesce(eu.content_text,'')), 1) = ':'
      and cardinality(
        regexp_split_to_array(
          trim(regexp_replace(coalesce(eu.content_text,''), '\s+', ' ', 'g')),
          '\s+'
        )
      ) between 1 and 10
    )
  );

-- Domain row: lifecycle, never destructive delete.
update public.project_strategy_elements pse
set lifecycle_status = 'invalidated',
    attributes = coalesce(pse.attributes,'{}'::jsonb) || jsonb_build_object(
      'invalidated_by','V28.7.2B2',
      'invalidation_reason','adjacent_explicit_group_crossed_section_boundary',
      'invalidated_at',now()
    ),
    updated_at = now()
from nave_v2872b2_invalid_strategy bad
where pse.id = bad.strategy_id;

-- Governance mirrors the invalidation.
update public.domain_object_governance g
set lifecycle_status = 'invalidated',
    lifecycle_reason = 'V28.7.2B2: adjacent explicit Strategy group crossed a new section boundary',
    lifecycle_at = now(),
    metadata = coalesce(g.metadata,'{}'::jsonb) || jsonb_build_object(
      'invalidated_by','V28.7.2B2',
      'repair_kind','strategy_group_boundary'
    ),
    updated_at = now()
from nave_v2872b2_invalid_strategy bad
where g.entity_id = bad.entity_id;

-- Universal mirror is kept for history but no longer active.
update public.knowledge_entities ke
set status = 'inactive',
    valid_to = coalesce(ke.valid_to, now()),
    attributes = coalesce(ke.attributes,'{}'::jsonb) || jsonb_build_object(
      'invalidated_by','V28.7.2B2',
      'invalidation_reason','adjacent_explicit_group_crossed_section_boundary'
    ),
    updated_at = now()
from nave_v2872b2_invalid_strategy bad
where ke.id = bad.entity_id;

-- The originating observation is superseded, not deleted.
update public.semantic_observations so
set status = 'superseded',
    resolution_action = 'none',
    resolved_entity_id = null,
    resolved_domain_table = null,
    resolved_domain_id = null,
    resolution_detail = coalesce(so.resolution_detail,'{}'::jsonb) || jsonb_build_object(
      'superseded_by','V28.7.2B2',
      'reason','adjacent_explicit_group_crossed_section_boundary',
      'repaired_at',now()
    ),
    updated_at = now()
from nave_v2872b2_invalid_strategy bad
where so.id = bad.source_observation_id;

-- Any graph edge touching a now-invalid Strategy mirror must stop being active.
-- relation_evidence is intentionally preserved for historical auditability.
update public.knowledge_relations kr
set status = 'superseded',
    valid_to = coalesce(kr.valid_to, now()),
    attributes = coalesce(kr.attributes,'{}'::jsonb) || jsonb_build_object(
      'superseded_by','V28.7.2B2',
      'reason','relation_touched_invalidated_strategy_entity'
    ),
    updated_at = now()
where kr.status = 'active'
  and (
    kr.source_entity_id in (select entity_id from nave_v2872b2_invalid_strategy)
    or kr.target_entity_id in (select entity_id from nave_v2872b2_invalid_strategy)
  );

commit;

-- Readout: expected Chambinho repair is 4 rows, but this SQL is generic and
-- only acts on B1 adjacent-group leakage patterns.
select
  count(*)::integer as invalidated_strategy_rows,
  coalesce(jsonb_agg(
    jsonb_build_object(
      'project_id', project_id,
      'strategy_id', strategy_id,
      'entity_id', entity_id,
      'strategy_type', strategy_type,
      'title', title,
      'evidence_text', evidence_text
    )
    order by project_id, lower(title)
  ), '[]'::jsonb) as invalidated_rows
from nave_v2872b2_invalid_strategy;
