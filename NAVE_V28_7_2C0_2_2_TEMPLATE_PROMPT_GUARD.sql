-- NAVE by VOE · V28.7.2C0.2.2 — Template Prompt Guard & Lifecycle Alignment
-- Incremental patch over C0.2/C0.2.1.
--
-- Fixes a false-positive proven by Golden Chambinho:
-- unanswered briefing form prompts containing words such as "devem" must not become
-- evidence-led Requirement identities.
--
-- Also aligns stale evidence-led lifecycle across governance, project_requirements
-- and knowledge_entities. No DELETE. No Graph V28.6 rebuild. No domain_primary.

begin;

create or replace view public.project_requirement_truth_status
with (security_invoker = true)
as
with base as (
  select
    pr.*,
    coalesce(g.lifecycle_status,'active') as lifecycle_status,
    coalesce(g.review_status,'unreviewed') as review_status,
    exists (
      select 1
      from public.domain_object_evidence doe
      join public.evidence_units eu
        on eu.id=doe.evidence_unit_id and eu.is_current=true
      where doe.object_entity_id=pr.entity_id
        and doe.domain_table='project_requirements'
        and doe.domain_id=pr.id
        and doe.link_role in ('source','supports','occurrence')
    ) as has_direct_domain_evidence,
    exists (
      select 1
      from public.project_requirement_occurrences pro
      join public.evidence_units eu
        on eu.id=pro.evidence_unit_id and eu.is_current=true
      where pro.requirement_id=pr.id
        and pro.lifecycle_status='active'
    ) as has_current_occurrence
  from public.project_requirements pr
  left join public.domain_object_governance g on g.entity_id=pr.entity_id
), explained as (
  select
    b.*,
    lo.semantic_role as legacy_explanation_role,
    lo.status as legacy_explanation_status,
    lo.resolution_action as legacy_explanation_action,
    lo.evidence_unit_id as legacy_explanation_evidence_id
  from base b
  left join lateral (
    select so.semantic_role,so.status,so.resolution_action,so.evidence_unit_id,so.attributes,so.updated_at
    from public.semantic_observations so
    where so.project_id=b.project_id
      and so.domain_hint='requirement'
      and coalesce(so.attributes->>'origin_route','')='legacy_recall'
      and coalesce(so.attributes->>'legacy_requirement_id','') in (
        coalesce(b.legacy_source_id::text,''), b.id::text
      )
      and so.status <> 'superseded'
    order by so.updated_at desc, so.id desc
    limit 1
  ) lo on true
)
select
  e.*,
  (e.has_direct_domain_evidence or e.has_current_occurrence) as has_current_evidence,
  case
    when e.lifecycle_status <> 'active' or e.status in ('superseded','cancelled') then 'historical'
    when e.review_status = 'rejected' then 'conflicted'
    when e.review_status in ('confirmed','corrected') then 'human_confirmed'
    when e.legacy_explanation_status = 'review_required' then 'review_required'
    when e.legacy_explanation_status = 'no_domain_object'
      or e.legacy_explanation_role in (
        'channel_scope','platform_scope','deliverable_scope',
        'product_attribute','experience_attribute',
        'audience_context','strategy_context','reference_signal','solution_reference','form_prompt'
      ) then 'legacy_unverified'
    when e.has_current_occurrence then 'verified'
    else 'legacy_unverified'
  end as truth_state,
  (
    select so.attributes->>'origin_route'
    from public.semantic_observations so
    where so.project_id=e.project_id
      and so.domain_hint='requirement'
      and coalesce(so.attributes->>'origin_route','')='legacy_recall'
      and coalesce(so.attributes->>'legacy_requirement_id','') in (
        coalesce(e.legacy_source_id::text,''), e.id::text
      )
      and so.status <> 'superseded'
    order by so.updated_at desc, so.id desc
    limit 1
  ) as legacy_explanation_origin_route
from explained e;


create or replace view public.project_requirement_reconciliation_status
with (security_invoker = true)
as
select
  p.id as project_id,
  (select count(*)::integer from public.project_requirement_truth_status t where t.project_id=p.id and t.truth_state <> 'historical') as requirement_identities,
  (select count(*)::integer from public.project_requirement_truth_status t where t.project_id=p.id and t.truth_state='verified') as verified,
  (select count(*)::integer from public.project_requirement_truth_status t where t.project_id=p.id and t.truth_state='human_confirmed') as human_confirmed,
  (select count(*)::integer from public.project_requirement_truth_status t where t.project_id=p.id and t.truth_state='legacy_unverified') as legacy_unverified,
  (select count(*)::integer from public.project_requirement_truth_status t where t.project_id=p.id and t.truth_state='review_required') as review_required,
  (select count(*)::integer from public.project_requirement_truth_status t where t.project_id=p.id and t.truth_state='conflicted') as conflicted,
  (
    select count(*)::integer from public.project_requirement_occurrences pro
    join public.evidence_units eu on eu.id=pro.evidence_unit_id and eu.is_current=true
    where pro.project_id=p.id and pro.lifecycle_status='active'
  ) as occurrences_with_evidence,
  (select count(*)::integer from public.project_requirement_constraints prc where prc.project_id=p.id and prc.status='active') as constraints_with_evidence,
  (
    select count(*)::integer from public.semantic_observations so
    where so.project_id=p.id and so.domain_hint='requirement' and so.status <> 'superseded'
  ) as semantic_observations,
  (
    select count(*)::integer from public.semantic_observations so
    where so.project_id=p.id and so.domain_hint='requirement' and so.status='open'
  ) as observations_open,
  (
    select count(*)::integer from public.semantic_observations so
    where so.project_id=p.id and so.domain_hint='requirement' and so.status='reconciled'
  ) as observations_reconciled,
  (
    select count(*)::integer from public.semantic_observations so
    where so.project_id=p.id and so.domain_hint='requirement' and so.status='no_domain_object'
  ) as observations_no_domain,
  (
    select count(*)::integer from public.semantic_observations so
    where so.project_id=p.id and so.domain_hint='requirement' and so.status='review_required'
  ) as observations_review_required,
  (
    select count(*)::integer from public.semantic_observations so
    where so.project_id=p.id and so.domain_hint='requirement' and so.status <> 'superseded'
      and so.semantic_role in ('channel_scope','platform_scope','deliverable_scope')
  ) as classified_scope,
  (
    select count(*)::integer from public.semantic_observations so
    where so.project_id=p.id and so.domain_hint='requirement' and so.status <> 'superseded'
      and so.semantic_role in ('product_attribute','experience_attribute')
  ) as classified_attribute,
  (
    select count(*)::integer from public.semantic_observations so
    where so.project_id=p.id and so.domain_hint='requirement' and so.status <> 'superseded'
      and so.semantic_role in ('audience_context','strategy_context','form_prompt')
  ) as classified_context,
  (
    select count(*)::integer
    from public.project_requirement_truth_status t
    where t.project_id=p.id and t.truth_state='legacy_unverified' and t.legacy_explanation_role is not null
  ) as explained_legacy_shadow,
  (
    select count(*)::integer
    from public.project_requirement_truth_status t
    where t.project_id=p.id and t.truth_state='legacy_unverified' and t.legacy_explanation_role is null
  ) as unexplained_legacy_shadow,
  case
    when (select count(*) from public.project_requirement_truth_status t where t.project_id=p.id and t.truth_state <> 'historical')=0 then 0::numeric
    else round(
      100.0 * (
        select count(*) from public.project_requirement_truth_status t
        where t.project_id=p.id and t.truth_state in ('verified','human_confirmed')
      ) / nullif((select count(*) from public.project_requirement_truth_status t where t.project_id=p.id and t.truth_state <> 'historical'),0),
      2
    )
  end as verified_coverage_pct,
  '28.7.2c0.2.2'::text as domain_schema_version,
  (select migration_mode from public.project_domain_migration_state pdms where pdms.project_id=p.id) as migration_mode,
  (
    select ir.id
    from public.intelligence_runs ir
    join public.knowledge_entities pe on pe.id=ir.scope_entity_id and pe.domain_table='projects' and pe.domain_id=p.id
    where ir.analyzer_type='project_requirement_reconciliation' and ir.status='completed'
    order by ir.created_at desc limit 1
  ) as last_completed_run_id,

  -- C0.2-only columns appended after the entire C0 contract.
  (select count(*)::integer from public.project_requirement_truth_status t
    where t.project_id=p.id and t.legacy_source_id is not null and t.truth_state <> 'historical'
  ) as legacy_requirement_rows,
  (select count(*)::integer from public.project_requirement_truth_status t
    where t.project_id=p.id and t.truth_state in ('verified','human_confirmed','review_required')
  ) as current_requirement_identities,
  (
    select count(*)::integer from public.semantic_observations so
    where so.project_id=p.id and so.domain_hint='requirement' and so.status <> 'superseded'
      and coalesce(so.attributes->>'origin_route','')='legacy_recall'
  ) as legacy_recall_observations,
  (
    select count(*)::integer from public.semantic_observations so
    where so.project_id=p.id and so.domain_hint='requirement' and so.status <> 'superseded'
      and coalesce(so.attributes->>'origin_route','')='evidence_first'
  ) as evidence_first_observations,
  (
    select count(*)::integer from public.semantic_observations so
    where so.project_id=p.id and so.domain_hint='requirement' and so.status <> 'superseded'
      and so.semantic_role in ('reference_signal','solution_reference')
  ) as classified_reference,
  (
    select count(*)::integer from public.semantic_observations so
    where so.project_id=p.id and so.domain_hint='requirement' and so.status <> 'superseded'
      and so.semantic_role='constraint_candidate'
  ) as classified_constraint,
  (
    select count(*)::integer from public.project_requirements pr
    where pr.project_id=p.id and pr.legacy_source_id is null
      and coalesce(pr.attributes->>'origin','') like 'evidence_led_v2872c0%'
  ) as evidence_led_requirement_identities
from public.projects p;


create or replace function public.apply_project_requirement_reconciliation_v2872c0(
  p_project_id uuid,
  p_run_id uuid,
  p_bundle jsonb
)
returns jsonb
language plpgsql
security invoker
set search_path = public
as $$
declare
  v_item jsonb;
  v_domain_id uuid;
  v_entity_id uuid;
  v_project_entity_id uuid;
  v_observation_count integer := 0;
  v_requirement_count integer := 0;
  v_occurrence_count integer := 0;
  v_evidence_link_count integer := 0;
  v_resolution_count integer := 0;
  v_superseded_observations integer := 0;
  v_superseded_occurrences integer := 0;
  v_evidence_first_count integer := 0;
  v_legacy_recall_count integer := 0;
begin
  if p_project_id is null or p_run_id is null then
    raise exception 'V28.7.2C0.2.2 requires project_id and run_id';
  end if;

  select id into v_project_entity_id
  from public.knowledge_entities
  where domain_table='projects' and domain_id=p_project_id
  order by created_at asc
  limit 1;
  if v_project_entity_id is null then
    raise exception 'V28.7.2C0.2.2 project knowledge_entity missing';
  end if;

  -- Fail closed. Existing legacy Requirements may not be semantically erased by an
  -- empty bundle caused by a missing/failed source extraction.
  if jsonb_array_length(coalesce(p_bundle->'observations','[]'::jsonb)) = 0
     and exists (select 1 from public.project_requirements pr where pr.project_id=p_project_id) then
    raise exception 'V28.7.2C0.2.2 empty observation bundle blocked';
  end if;

  select count(*)::integer into v_evidence_first_count
  from jsonb_array_elements(coalesce(p_bundle->'observations','[]'::jsonb)) x
  where coalesce(x.value->'attributes'->>'origin_route','')='evidence_first';

  select count(*)::integer into v_legacy_recall_count
  from jsonb_array_elements(coalesce(p_bundle->'observations','[]'::jsonb)) x
  where coalesce(x.value->'attributes'->>'origin_route','')='legacy_recall';

  -- Supersede stale C0 observations from earlier generations. Preserve history.
  update public.semantic_observations so
  set status='superseded', resolution_action='none', resolution_run_id=p_run_id, updated_at=now()
  where so.project_id=p_project_id
    and so.domain_hint='requirement'
    and coalesce(so.attributes->>'normalized_by','') like 'V28.7.2C0%'
    and not exists (
      select 1 from jsonb_array_elements(coalesce(p_bundle->'observations','[]'::jsonb)) x
      where x.value->>'id'=so.id::text
    );
  get diagnostics v_superseded_observations = row_count;

  -- Supersede stale C0 occurrences before re-activating this run's canonical set.
  update public.project_requirement_occurrences pro
  set lifecycle_status='superseded', normalization_run_id=p_run_id, updated_at=now()
  where pro.project_id=p_project_id
    and coalesce(pro.attributes->>'normalized_by','') like 'V28.7.2C0%'
    and not exists (
      select 1 from jsonb_array_elements(coalesce(p_bundle->'occurrences','[]'::jsonb)) x
      where x.value->>'occurrence_hash'=pro.occurrence_hash
    );
  get diagnostics v_superseded_occurrences = row_count;

  -- Semantic observations: staging, never current truth by themselves.
  for v_item in select value from jsonb_array_elements(coalesce(p_bundle->'observations','[]'::jsonb))
  loop
    insert into public.semantic_observations(
      id,project_id,source_asset_id,evidence_unit_id,observation_kind,observed_name,
      observed_type,observed_status,occurrence_phase,occurrence_role,
      domain_hint,semantic_role,assertion_mode,attributes,source_authority_score,
      model_confidence,extraction_method,observation_hash,status,intelligence_run_id
    ) values (
      (v_item->>'id')::uuid,p_project_id,(v_item->>'source_asset_id')::uuid,(v_item->>'evidence_unit_id')::uuid,
      coalesce(nullif(v_item->>'observation_kind',''),'requirement_signal'),
      coalesce(nullif(v_item->>'observed_name',''),'Requisito'),nullif(v_item->>'observed_type',''),nullif(v_item->>'observed_status',''),
      coalesce(nullif(v_item->>'occurrence_phase',''),'reference'),coalesce(nullif(v_item->>'occurrence_role',''),'reference'),
      'requirement',nullif(v_item->>'semantic_role',''),coalesce(nullif(v_item->>'assertion_mode',''),'source_explicit'),
      coalesce(v_item->'attributes','{}'::jsonb),nullif(v_item->>'source_authority_score','')::numeric,
      nullif(v_item->>'model_confidence','')::numeric,coalesce(nullif(v_item->>'extraction_method',''),'requirement_reconciliation'),
      v_item->>'observation_hash','open',p_run_id
    )
    on conflict (observation_hash) do update set
      domain_hint='requirement',
      semantic_role=excluded.semantic_role,
      observed_name=excluded.observed_name,
      observed_type=excluded.observed_type,
      occurrence_phase=excluded.occurrence_phase,
      occurrence_role=excluded.occurrence_role,
      assertion_mode=excluded.assertion_mode,
      attributes=coalesce(public.semantic_observations.attributes,'{}'::jsonb)||excluded.attributes,
      source_authority_score=greatest(coalesce(public.semantic_observations.source_authority_score,0),coalesce(excluded.source_authority_score,0)),
      model_confidence=excluded.model_confidence,
      extraction_method=excluded.extraction_method,
      status='open',
      resolution_action='none',
      resolved_entity_id=null,
      resolved_domain_table=null,
      resolved_domain_id=null,
      resolution_detail='{}'::jsonb,
      resolution_run_id=null,
      intelligence_run_id=excluded.intelligence_run_id,
      updated_at=now();
    v_observation_count := v_observation_count + 1;
  end loop;

  -- New evidence-led Requirement identities. Existing identities are never merged.
  for v_item in select value from jsonb_array_elements(coalesce(p_bundle->'requirements','[]'::jsonb))
  loop
    v_domain_id := (v_item->>'id')::uuid;
    v_entity_id := (v_item->>'entity_id')::uuid;

    insert into public.knowledge_entities(
      id,entity_type,canonical_name,normalized_name,entity_kind,scope_entity_id,
      domain_table,domain_id,attributes,status,confidence
    ) values (
      v_entity_id,'requirement',coalesce(nullif(v_item->>'title',''),'Requisito'),
      coalesce(nullif(v_item->>'normalized_name',''),lower(coalesce(nullif(v_item->>'title',''),'requisito'))),
      'project_instance',v_project_entity_id,'project_requirements',v_domain_id,
      jsonb_build_object('projection_only',true,'normalized_by','V28.7.2C0.2.2','origin','evidence_led_v2872c0_2'),
      'active',nullif(v_item->>'confidence','')::numeric
    )
    on conflict (domain_table,domain_id) where domain_table is not null and domain_id is not null
    do update set
      canonical_name=excluded.canonical_name,
      normalized_name=excluded.normalized_name,
      scope_entity_id=excluded.scope_entity_id,
      attributes=coalesce(public.knowledge_entities.attributes,'{}'::jsonb)||excluded.attributes,
      status='active',
      confidence=greatest(coalesce(public.knowledge_entities.confidence,0),coalesce(excluded.confidence,0)),
      updated_at=now();

    insert into public.project_requirements(
      id,project_id,entity_id,requirement_type,title,description,priority,mandatory,
      constraint_operator,constraint_value,unit,status,confidence,attributes,
      legacy_source_table,legacy_source_id
    ) values (
      v_domain_id,p_project_id,v_entity_id,coalesce(nullif(v_item->>'requirement_type',''),'other'),
      coalesce(nullif(v_item->>'title',''),'Requisito'),nullif(v_item->>'description',''),
      coalesce(nullif(v_item->>'priority',''),'not_informed'),coalesce((v_item->>'mandatory')::boolean,false),
      null,null,null,'active',nullif(v_item->>'confidence','')::numeric,
      coalesce(v_item->'attributes','{}'::jsonb),null,null
    )
    on conflict (id) do update set
      entity_id=excluded.entity_id,
      requirement_type=case when public.nave_domain_field_locked(public.project_requirements.entity_id,'requirement_type',coalesce(nullif(v_item->>'source_authority_score','')::numeric,0.82)) then public.project_requirements.requirement_type else excluded.requirement_type end,
      title=case when public.nave_domain_field_locked(public.project_requirements.entity_id,'title',coalesce(nullif(v_item->>'source_authority_score','')::numeric,0.82)) then public.project_requirements.title else excluded.title end,
      description=case when public.nave_domain_field_locked(public.project_requirements.entity_id,'description',coalesce(nullif(v_item->>'source_authority_score','')::numeric,0.82)) then public.project_requirements.description else coalesce(excluded.description,public.project_requirements.description) end,
      mandatory=case when public.nave_domain_field_locked(public.project_requirements.entity_id,'mandatory',coalesce(nullif(v_item->>'source_authority_score','')::numeric,0.82)) then public.project_requirements.mandatory else excluded.mandatory end,
      status='active',
      confidence=greatest(coalesce(public.project_requirements.confidence,0),coalesce(excluded.confidence,0)),
      attributes=coalesce(public.project_requirements.attributes,'{}'::jsonb)||excluded.attributes,
      updated_at=now();

    insert into public.domain_object_governance(
      entity_id,project_id,lifecycle_status,review_status,source_authority_score,
      model_confidence,field_authority,last_normalization_run_id,metadata
    ) values (
      v_entity_id,p_project_id,'active','unreviewed',nullif(v_item->>'source_authority_score','')::numeric,
      nullif(v_item->>'confidence','')::numeric,
      jsonb_build_object(
        'requirement_type',coalesce(nullif(v_item->>'source_authority_score','')::numeric,0.82),
        'title',coalesce(nullif(v_item->>'source_authority_score','')::numeric,0.82),
        'description',coalesce(nullif(v_item->>'source_authority_score','')::numeric,0.82),
        'mandatory',coalesce(nullif(v_item->>'source_authority_score','')::numeric,0.82)
      ),
      p_run_id,jsonb_build_object('normalized_by','V28.7.2C0.2.2','source_layer','evidence_led')
    )
    on conflict (entity_id) do update set
      lifecycle_status='active',
      source_authority_score=greatest(coalesce(public.domain_object_governance.source_authority_score,0),coalesce(excluded.source_authority_score,0)),
      model_confidence=greatest(coalesce(public.domain_object_governance.model_confidence,0),coalesce(excluded.model_confidence,0)),
      field_authority=public.nave_merge_field_authority(public.domain_object_governance.field_authority,excluded.field_authority),
      last_normalization_run_id=p_run_id,
      metadata=coalesce(public.domain_object_governance.metadata,'{}'::jsonb)||excluded.metadata,
      updated_at=now();
    v_requirement_count := v_requirement_count + 1;
  end loop;

  -- Current canonical occurrence set.
  for v_item in select value from jsonb_array_elements(coalesce(p_bundle->'occurrences','[]'::jsonb))
  loop
    insert into public.project_requirement_occurrences(
      id,project_id,requirement_id,legacy_requirement_id,source_asset_id,evidence_unit_id,
      semantic_observation_id,occurrence_phase,occurrence_role,observed_text,observed_type,
      scope_json,attributes,confidence,lifecycle_status,occurrence_hash,normalization_run_id
    ) values (
      (v_item->>'id')::uuid,p_project_id,(v_item->>'requirement_id')::uuid,
      nullif(v_item->>'legacy_requirement_id','')::uuid,(v_item->>'source_asset_id')::uuid,(v_item->>'evidence_unit_id')::uuid,
      nullif(v_item->>'semantic_observation_id','')::uuid,coalesce(nullif(v_item->>'occurrence_phase',''),'reference'),
      coalesce(nullif(v_item->>'occurrence_role',''),'requirement'),coalesce(nullif(v_item->>'observed_text',''),'Requisito'),
      nullif(v_item->>'observed_type',''),coalesce(v_item->'scope_json','{}'::jsonb),coalesce(v_item->'attributes','{}'::jsonb),
      nullif(v_item->>'confidence','')::numeric,'active',v_item->>'occurrence_hash',p_run_id
    )
    on conflict (occurrence_hash) do update set
      requirement_id=excluded.requirement_id,
      legacy_requirement_id=coalesce(excluded.legacy_requirement_id,public.project_requirement_occurrences.legacy_requirement_id),
      semantic_observation_id=coalesce(excluded.semantic_observation_id,public.project_requirement_occurrences.semantic_observation_id),
      occurrence_role=excluded.occurrence_role,
      observed_text=excluded.observed_text,
      observed_type=coalesce(excluded.observed_type,public.project_requirement_occurrences.observed_type),
      scope_json=coalesce(public.project_requirement_occurrences.scope_json,'{}'::jsonb)||excluded.scope_json,
      attributes=coalesce(public.project_requirement_occurrences.attributes,'{}'::jsonb)||excluded.attributes,
      confidence=greatest(coalesce(public.project_requirement_occurrences.confidence,0),coalesce(excluded.confidence,0)),
      lifecycle_status='active',
      normalization_run_id=p_run_id,
      updated_at=now();
    v_occurrence_count := v_occurrence_count + 1;
  end loop;

  -- Domain provenance many-to-many. Old links are preserved as historical provenance;
  -- the Truth Gate no longer treats those links alone as Requirement truth.
  for v_item in select value from jsonb_array_elements(coalesce(p_bundle->'evidence_links','[]'::jsonb))
  loop
    insert into public.domain_object_evidence(
      project_id,object_entity_id,domain_table,domain_id,evidence_unit_id,link_role,
      context,context_sha256,binding_confidence,normalization_run_id
    ) values (
      p_project_id,(v_item->>'object_entity_id')::uuid,'project_requirements',(v_item->>'domain_id')::uuid,
      (v_item->>'evidence_unit_id')::uuid,coalesce(nullif(v_item->>'link_role',''),'occurrence'),
      coalesce(v_item->'context','{}'::jsonb),v_item->>'context_sha256',nullif(v_item->>'binding_confidence','')::numeric,p_run_id
    )
    on conflict (object_entity_id,evidence_unit_id,link_role,context_sha256)
    do update set
      binding_confidence=greatest(coalesce(public.domain_object_evidence.binding_confidence,0),coalesce(excluded.binding_confidence,0)),
      normalization_run_id=p_run_id,
      updated_at=now();
    v_evidence_link_count := v_evidence_link_count + 1;
  end loop;

  -- Resolution is last: a partial plan cannot look reconciled.
  for v_item in select value from jsonb_array_elements(coalesce(p_bundle->'observation_resolutions','[]'::jsonb))
  loop
    update public.semantic_observations
    set status=coalesce(nullif(v_item->>'status',''),'open'),
        resolution_action=coalesce(nullif(v_item->>'resolution_action',''),'none'),
        resolved_entity_id=nullif(v_item->>'resolved_entity_id','')::uuid,
        resolved_domain_table=nullif(v_item->>'resolved_domain_table',''),
        resolved_domain_id=nullif(v_item->>'resolved_domain_id','')::uuid,
        resolution_detail=coalesce(resolution_detail,'{}'::jsonb)||coalesce(v_item->'resolution_detail','{}'::jsonb),
        resolution_run_id=p_run_id,
        updated_at=now()
    where id=(v_item->>'id')::uuid and project_id=p_project_id;
    v_resolution_count := v_resolution_count + 1;
  end loop;

  -- Evidence-led identities that disappeared from the canonical source remain in history,
  -- but no longer present as active current Requirements unless Human Review locked them.
  update public.domain_object_governance g
  set lifecycle_status='superseded',last_normalization_run_id=p_run_id,updated_at=now()
  from public.project_requirements pr
  where pr.entity_id=g.entity_id
    and pr.project_id=p_project_id
    and pr.legacy_source_id is null
    and coalesce(pr.attributes->>'origin','') like 'evidence_led_v2872c0%'
    and coalesce(g.review_status,'unreviewed') not in ('confirmed','corrected')
    and not exists (
      select 1 from public.project_requirement_occurrences pro
      where pro.requirement_id=pr.id and pro.lifecycle_status='active'
    );

  -- Keep the projected domain row and Knowledge Entity lifecycle aligned with
  -- governance when an evidence-led Requirement disappears from the current source.
  update public.project_requirements pr
  set status='superseded',updated_at=now()
  where pr.project_id=p_project_id
    and pr.legacy_source_id is null
    and coalesce(pr.attributes->>'origin','') like 'evidence_led_v2872c0%'
    and exists (
      select 1 from public.domain_object_governance g
      where g.entity_id=pr.entity_id
        and g.lifecycle_status='superseded'
        and coalesce(g.review_status,'unreviewed') not in ('confirmed','corrected')
    )
    and not exists (
      select 1 from public.project_requirement_occurrences pro
      where pro.requirement_id=pr.id and pro.lifecycle_status='active'
    );

  update public.knowledge_entities ke
  set status='inactive',updated_at=now()
  from public.project_requirements pr
  where pr.entity_id=ke.id
    and pr.project_id=p_project_id
    and pr.legacy_source_id is null
    and coalesce(pr.attributes->>'origin','') like 'evidence_led_v2872c0%'
    and pr.status='superseded'
    and not exists (
      select 1 from public.project_requirement_occurrences pro
      where pro.requirement_id=pr.id and pro.lifecycle_status='active'
    );

  update public.intelligence_runs
  set status='completed',completed_at=now(),
      output_signature=pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(coalesce(p_bundle,'{}'::jsonb)::text,'UTF8')),'hex'),
      metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
        'requirement_observations',v_observation_count,
        'legacy_recall_observations',v_legacy_recall_count,
        'evidence_first_observations',v_evidence_first_count,
        'new_requirements',v_requirement_count,
        'requirement_occurrences',v_occurrence_count,
        'evidence_links',v_evidence_link_count,
        'resolutions',v_resolution_count,
        'superseded_observations',v_superseded_observations,
        'superseded_occurrences',v_superseded_occurrences,
        'legacy_shadow',true,
        'auto_merge_existing_requirements',false,
        'evidence_first_requirement_inventory',true
      )
  where id=p_run_id;

  return jsonb_build_object(
    'status','completed',
    'observations',v_observation_count,
    'legacy_recall_observations',v_legacy_recall_count,
    'evidence_first_observations',v_evidence_first_count,
    'new_requirements',v_requirement_count,
    'occurrences',v_occurrence_count,
    'evidence_links',v_evidence_link_count,
    'resolutions',v_resolution_count,
    'superseded_observations',v_superseded_observations,
    'superseded_occurrences',v_superseded_occurrences
  );
exception when others then
  raise;
end;
$$;


comment on view public.project_requirement_truth_status is
  'V28.7.2C0.2.2 — Requirement Truth Gate; form/template prompts are no-domain and historical Evidence is provenance, not semantic identity.';

comment on view public.project_requirement_reconciliation_status is
  'V28.7.2C0.2.2 — Requirement debugger with evidence-first discovery, semantic no-domain roles and template-prompt context classification.';

comment on function public.apply_project_requirement_reconciliation_v2872c0(uuid,uuid,jsonb) is
  'V28.7.2C0.2.2 — atomic evidence-first Requirement reconciliation; stale evidence-led identities are superseded consistently across occurrence, governance, domain row and Knowledge Entity.';

revoke all on public.project_requirement_truth_status from anon, authenticated;
revoke all on public.project_requirement_reconciliation_status from anon, authenticated;
grant select on public.project_requirement_truth_status to service_role, postgres;
grant select on public.project_requirement_reconciliation_status to service_role, postgres;

revoke all on function public.apply_project_requirement_reconciliation_v2872c0(uuid,uuid,jsonb)
  from public, anon, authenticated;
grant execute on function public.apply_project_requirement_reconciliation_v2872c0(uuid,uuid,jsonb)
  to service_role, postgres;

notify pgrst, 'reload schema';

commit;

select
  'V28.7.2C0.2.2 installed'::text as status,
  to_regprocedure('public.apply_project_requirement_reconciliation_v2872c0(uuid,uuid,jsonb)') is not null as rpc_ok,
  exists (
    select 1
    from information_schema.columns
    where table_schema='public'
      and table_name='project_requirement_reconciliation_status'
      and column_name='classified_context'
  ) as view_contract_ok;
