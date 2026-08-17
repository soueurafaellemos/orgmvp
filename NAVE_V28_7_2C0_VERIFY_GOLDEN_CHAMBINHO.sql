-- NAVE by VOE · V28.7.2C0 — Golden Chambinho Requirement reconciliation verification
-- READ ONLY. Returns one row for CSV export.
-- The Golden UUID is intentional because the database historically contains another
-- project row with the same display name.

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
), requirement_status as (
  select s.*
  from public.project_requirement_reconciliation_status s
  join tp on tp.project_id=s.project_id
), requirement_truth as (
  select t.*
  from public.project_requirement_truth_status t
  join tp on tp.project_id=t.project_id
), c0_observations as (
  select so.*,eu.is_current as evidence_is_current
  from public.semantic_observations so
  join tp on tp.project_id=so.project_id
  left join public.evidence_units eu on eu.id=so.evidence_unit_id
  where so.domain_hint='requirement' and so.status <> 'superseded'
), c0_requirements as (
  select pr.*
  from public.project_requirements pr
  join tp on tp.project_id=pr.project_id
  where coalesce(pr.attributes->>'origin','')='evidence_led_v2872c0'
), c0_occurrences as (
  select pro.*
  from public.project_requirement_occurrences pro
  join tp on tp.project_id=pro.project_id
  where pro.lifecycle_status='active'
), latest_runs as (
  select * from (
    select ir.id,ir.analyzer_type,ir.status,ir.created_at,ir.metadata,
           row_number() over(partition by ir.analyzer_type order by ir.created_at desc,ir.id desc) as rn
    from public.intelligence_runs ir
    join project_entity pe on pe.entity_id=ir.scope_entity_id
    where ir.analyzer_type in ('project_requirement_reconciliation','project_core_semantic_domains','cross_source_linker')
  ) x where rn=1
), regression as (
  select
    (select count(*)::integer from public.project_solution_instances psi join tp on tp.project_id=psi.project_id) as solutions,
    (select count(*)::integer from public.entity_current_outcomes eco join tp on tp.project_id=eco.project_id where eco.outcome_type='execution_status' and eco.outcome_status='executed') as executed_truths,
    (select count(*)::integer from public.financial_line_items fli join tp on tp.project_id=fli.project_id) as financial_lines,
    (select count(*)::integer from public.financial_line_items fli join tp on tp.project_id=fli.project_id where fli.source_evidence_id is not null) as financial_lines_with_evidence,
    (select count(*)::integer from public.memory_briefing_requirements mbr join tp on tp.project_id=mbr.project_id) as legacy_requirements
), checks as (
  select jsonb_build_object(
    'project_found',exists(select 1 from tp),
    'migration_is_legacy_shadow',coalesce((select migration_mode='legacy_shadow' from requirement_status),false),
    'c0_schema_visible',coalesce((select domain_schema_version='28.7.2c0' from requirement_status),false),
    'c0_run_completed',exists(select 1 from latest_runs where analyzer_type='project_requirement_reconciliation' and status='completed'),
    'requirements_preserved_14',coalesce((select requirement_identities=14 from requirement_status),false),
    'legacy_requirements_still_14',(select legacy_requirements=14 from regression),
    'all_requirements_verified_or_human',coalesce((select verified+human_confirmed=14 from requirement_status),false),
    'no_legacy_unverified',coalesce((select legacy_unverified=0 from requirement_status),false),
    'no_unexplained_shadow',coalesce((select unexplained_legacy_shadow=0 from requirement_status),false),
    'no_requirement_review_or_conflict',coalesce((select review_required=0 and conflicted=0 from requirement_status),false),
    'c0_did_not_inflate_requirements',not exists(select 1 from c0_requirements),
    'requirement_occurrences_are_evidence_backed',not exists(
      select 1 from c0_occurrences pro
      left join public.evidence_units eu on eu.id=pro.evidence_unit_id
      where coalesce(eu.is_current,false)=false
    ),
    'all_c0_observations_have_current_evidence',not exists(select 1 from c0_observations where coalesce(evidence_is_current,false)=false),
    'constraints_preserved',coalesce((select constraints_with_evidence>=2 from requirement_status),false),
    'solutions_preserved_19',(select solutions=19 from regression),
    'execution_truths_preserved_8',(select executed_truths=8 from regression),
    'finance_preserved_54',(select financial_lines=54 and financial_lines_with_evidence=54 from regression),
    'c0_never_auto_merges_existing_requirements',coalesce((
      select coalesce((metadata->>'auto_merge_existing_requirements')::boolean,false)=false
      from latest_runs where analyzer_type='project_requirement_reconciliation'
    ),false),
    'graph_v28_6_not_rerun_after_c0',coalesce(
      (select created_at from latest_runs where analyzer_type='cross_source_linker') <
      (select created_at from latest_runs where analyzer_type='project_requirement_reconciliation'),true
    )
  ) as result
)
select
  (select to_jsonb(p) from target_project p) as project,
  (select to_jsonb(s) from requirement_status s) as requirement_status,
  (select result from checks) as gate_checks,
  (select to_jsonb(r) from regression r) as regression_snapshot,
  coalesce((
    select jsonb_agg(jsonb_build_object(
      'id',t.id,'title',t.title,'requirement_type',t.requirement_type,
      'truth_state',t.truth_state,'has_current_evidence',t.has_current_evidence,
      'legacy_explanation_role',t.legacy_explanation_role,
      'legacy_explanation_status',t.legacy_explanation_status,
      'legacy_explanation_action',t.legacy_explanation_action
    ) order by lower(t.title))
    from requirement_truth t
  ),'[]'::jsonb) as requirements,
  coalesce((select jsonb_agg(to_jsonb(x) order by x.created_at desc) from latest_runs x),'[]'::jsonb) as latest_runs;
