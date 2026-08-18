-- NAVE by VOE · V28.7.2C0.2.2 — Golden Chambinho verification
-- READ ONLY. Export the single result row as CSV and send it back for semantic audit.

with target_project as (
  select p.*
  from public.projects p
  where p.id='0d9f1608-4bf7-4fd0-81ab-f303fdb0c136'::uuid
  limit 1
), tp as (
  select id as project_id from target_project
), project_entity as (
  select ke.id as entity_id
  from public.knowledge_entities ke
  join tp on ke.domain_table='projects' and ke.domain_id=tp.project_id
  limit 1
), rs as (
  select s.* from public.project_requirement_reconciliation_status s join tp on tp.project_id=s.project_id
), rt as (
  select t.* from public.project_requirement_truth_status t join tp on tp.project_id=t.project_id
), obs as (
  select so.*,eu.is_current as evidence_is_current
  from public.semantic_observations so
  join tp on tp.project_id=so.project_id
  left join public.evidence_units eu on eu.id=so.evidence_unit_id
  where so.domain_hint='requirement' and so.status <> 'superseded'
), occ as (
  select pro.*,eu.is_current as evidence_is_current
  from public.project_requirement_occurrences pro
  join tp on tp.project_id=pro.project_id
  left join public.evidence_units eu on eu.id=pro.evidence_unit_id
  where pro.lifecycle_status='active'
), latest as (
  select * from (
    select ir.id,ir.analyzer_type,ir.status,ir.pipeline_version,ir.schema_version,ir.created_at,ir.metadata,
           row_number() over(partition by ir.analyzer_type order by ir.created_at desc,ir.id desc) rn
    from public.intelligence_runs ir
    join project_entity pe on pe.entity_id=ir.scope_entity_id
    where ir.analyzer_type in ('project_requirement_reconciliation','project_core_semantic_domains','cross_source_linker')
  ) x where rn=1
), regression as (
  select
    (select count(*)::integer from public.project_solution_instances psi join tp on tp.project_id=psi.project_id) solutions,
    (select count(*)::integer from public.entity_current_outcomes eco join tp on tp.project_id=eco.project_id where eco.outcome_type='execution_status' and eco.outcome_status='executed') executed_truths,
    (select count(*)::integer from public.financial_line_items fli join tp on tp.project_id=fli.project_id) financial_lines,
    (select count(*)::integer from public.financial_line_items fli join tp on tp.project_id=fli.project_id where fli.source_evidence_id is not null) financial_lines_with_evidence,
    (select count(*)::integer from public.memory_briefing_requirements mbr join tp on tp.project_id=mbr.project_id) legacy_requirements
), checks as (
  select jsonb_build_object(
    'project_found',exists(select 1 from tp),
    'migration_is_legacy_shadow',coalesce((select migration_mode='legacy_shadow' from rs),false),
    'c022_schema_visible',coalesce((select domain_schema_version='28.7.2c0.2.2' from rs),false),
    'c022_run_completed',exists(select 1 from latest where analyzer_type='project_requirement_reconciliation' and status='completed' and pipeline_version='V28.7.2C0.2.2'),
    'legacy_rows_preserved',(select legacy_requirements=14 from regression),
    'all_legacy_rows_passed_semantic_gate',coalesce((select legacy_recall_observations=legacy_requirement_rows from rs),false),
    'evidence_first_route_exercised',coalesce((select evidence_first_observations>0 from rs),false),
    'all_current_observations_have_current_evidence',not exists(select 1 from obs where coalesce(evidence_is_current,false)=false),
    'all_active_occurrences_have_current_evidence',not exists(select 1 from occ where coalesce(evidence_is_current,false)=false),
    'no_open_requirement_observations',coalesce((select observations_open=0 from rs),false),
    'no_unexplained_legacy_shadow',coalesce((select unexplained_legacy_shadow=0 from rs),false),
    'no_semantic_no_domain_requirement_is_verified',not exists(
      select 1 from rt
      where truth_state='verified'
        and (legacy_explanation_status='no_domain_object' or legacy_explanation_role in (
          'channel_scope','platform_scope','deliverable_scope','product_attribute','experience_attribute',
          'audience_context','strategy_context','reference_signal','solution_reference','form_prompt'
        ))
    ),
    'active_c0_occurrences_are_c022',not exists(
      select 1 from occ where coalesce(attributes->>'normalized_by','') <> 'V28.7.2C0.2.2'
    ),
    'evidence_led_current_requirements_have_active_occurrence',not exists(
      select 1 from rt t
      where t.legacy_source_id is null
        and coalesce(t.attributes->>'origin','') like 'evidence_led_v2872c0%'
        and t.truth_state in ('verified','human_confirmed','review_required')
        and not exists(select 1 from occ o where o.requirement_id=t.id)
    ),
    'no_existing_existing_auto_merge',coalesce((
      select coalesce((metadata->>'auto_merge_existing_requirements')::boolean,false)=false
      from latest where analyzer_type='project_requirement_reconciliation'
    ),false),
    'unanswered_template_prompt_not_current_requirement',not exists(
      select 1
      from rt t
      where t.truth_state in ('verified','human_confirmed','review_required')
        and lower(trim(coalesce(t.title,''))) ~ '^qual .+:[[:space:]]*\([^)]*\)[[:space:]]*$'
    ),
    'expected_current_requirement_identities_13',coalesce((select current_requirement_identities=13 from rs),false),
    'expected_verified_13',coalesce((select verified=13 from rs),false),
    'expected_legacy_unverified_2',coalesce((select legacy_unverified=2 from rs),false),
    'expected_evidence_led_current_requirements_1',coalesce((select evidence_led_requirement_identities=1 from rs),false),
    'expected_evidence_first_observations_2',coalesce((select evidence_first_observations=2 from rs),false),
    'expected_semantic_observations_16',coalesce((select semantic_observations=16 from rs),false),
    'expected_occurrences_with_evidence_13',coalesce((select occurrences_with_evidence=13 from rs),false),
    'solutions_preserved_19',(select solutions=19 from regression),
    'execution_truths_preserved_8',(select executed_truths=8 from regression),
    'finance_preserved_54',(select financial_lines=54 and financial_lines_with_evidence=54 from regression),
    'graph_v28_6_not_rerun_after_c022',coalesce(
      (select created_at from latest where analyzer_type='cross_source_linker') <
      (select created_at from latest where analyzer_type='project_requirement_reconciliation'),true
    )
  ) result
)
select
  (select to_jsonb(p) from target_project p) project,
  (select to_jsonb(s) from rs s) requirement_status,
  (select result from checks) gate_checks,
  (select to_jsonb(r) from regression r) regression_snapshot,
  coalesce((
    select jsonb_agg(jsonb_build_object(
      'id',t.id,'title',t.title,'requirement_type',t.requirement_type,'truth_state',t.truth_state,
      'legacy_source_id',t.legacy_source_id,'has_direct_domain_evidence',t.has_direct_domain_evidence,
      'has_current_occurrence',t.has_current_occurrence,'legacy_explanation_role',t.legacy_explanation_role,
      'legacy_explanation_status',t.legacy_explanation_status,'legacy_explanation_action',t.legacy_explanation_action
    ) order by t.truth_state,lower(t.title)) from rt t
  ),'[]'::jsonb) requirement_truth_inventory,
  coalesce((
    select jsonb_agg(jsonb_build_object(
      'id',so.id,'origin_route',so.attributes->>'origin_route','observed_name',so.observed_name,
      'semantic_role',so.semantic_role,'status',so.status,'resolution_action',so.resolution_action,
      'resolved_domain_id',so.resolved_domain_id,'evidence_unit_id',so.evidence_unit_id
    ) order by coalesce(so.attributes->>'origin_route',''),lower(so.observed_name)) from obs so
  ),'[]'::jsonb) current_requirement_observations,
  coalesce((select jsonb_agg(to_jsonb(x) order by x.created_at desc) from latest x),'[]'::jsonb) latest_runs;
