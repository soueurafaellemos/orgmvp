-- NAVE by VOE · V28.7.2C0.2.3 — Rerun Isolation & Truth Identity Fix
-- Incremental patch over C0.2.2.
--
-- Fixes an idempotence bug proven by the second Golden Chambinho run:
-- evidence-led Requirement identities from a prior C0 run were being fed back into
-- the legacy_recall route. Because legacy truth lookup also accepted an empty
-- legacy_requirement_id, a no-domain observation from one evidence-led identity
-- could contaminate the truth state of another evidence-led identity.
--
-- This SQL changes only the two read views. Runtime filtering is delivered in the
-- accompanying Python patch. No DELETE. No Graph V28.6 rebuild. No domain_primary.

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
      and b.legacy_source_id is not null
      and coalesce(so.attributes->>'origin_route','')='legacy_recall'
      and coalesce(so.attributes->>'legacy_requirement_id','')=b.legacy_source_id::text
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
      and e.legacy_source_id is not null
      and coalesce(so.attributes->>'origin_route','')='legacy_recall'
      and coalesce(so.attributes->>'legacy_requirement_id','')=e.legacy_source_id::text
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
  '28.7.2c0.2.3'::text as domain_schema_version,
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
    select count(*)::integer
    from public.project_requirement_truth_status t
    where t.project_id=p.id
      and t.legacy_source_id is null
      and coalesce(t.attributes->>'origin','') like 'evidence_led_v2872c0%'
      and t.truth_state in ('verified','human_confirmed','review_required')
  ) as evidence_led_requirement_identities
from public.projects p;

notify pgrst, 'reload schema';

commit;

select
  'V28.7.2C0.2.3 installed'::text as status,
  to_regclass('public.project_requirement_truth_status') is not null as truth_view_ok,
  to_regclass('public.project_requirement_reconciliation_status') is not null as status_view_ok;
