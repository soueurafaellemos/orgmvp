-- NAVE by VOE · V28.7.2C0.2 — Golden JOVI verification
-- READ ONLY. Run only after Golden Chambinho C0.2 is semantically approved.
-- Returns one row for CSV export.

with project_candidates as (
  select pf.project_id,
         count(*) filter(where lower(coalesce(pf.file_name,'')) like '%lancamento_jovi_x300%') proposal_matches,
         count(*) filter(where lower(coalesce(pf.file_name,'')) like '%briefing_jovi_x300%') briefing_matches,
         count(*) matched_files
  from public.project_files pf
  where lower(coalesce(pf.file_name,'')) like '%lancamento_jovi_x300%'
     or lower(coalesce(pf.file_name,'')) like '%briefing_jovi_x300%'
  group by pf.project_id
), target_project as (
  select p.*,pc.proposal_matches,pc.briefing_matches,pc.matched_files
  from project_candidates pc join public.projects p on p.id=pc.project_id
  order by (pc.proposal_matches>0 and pc.briefing_matches>0) desc,pc.matched_files desc,p.id
  limit 1
), tp as (
  select id as project_id from target_project
), project_entity as (
  select ke.id entity_id from public.knowledge_entities ke
  join tp on ke.domain_table='projects' and ke.domain_id=tp.project_id limit 1
), rs as (
  select s.* from public.project_requirement_reconciliation_status s join tp on tp.project_id=s.project_id
), rt as (
  select t.*,regexp_replace(lower(trim(t.title)),'[;:.]+$','','g') normalized_title
  from public.project_requirement_truth_status t join tp on tp.project_id=t.project_id
), obs as (
  select so.*,eu.is_current evidence_is_current
  from public.semantic_observations so join tp on tp.project_id=so.project_id
  left join public.evidence_units eu on eu.id=so.evidence_unit_id
  where so.domain_hint='requirement' and so.status <> 'superseded'
), occ as (
  select pro.*,eu.is_current evidence_is_current
  from public.project_requirement_occurrences pro join tp on tp.project_id=pro.project_id
  left join public.evidence_units eu on eu.id=pro.evidence_unit_id
  where pro.lifecycle_status='active'
), original_gap_titles(title) as (
  values
    ('criadores de conteúdo'),('filmmakers'),('fotógrafos'),('kwai'),('instagram'),('youtube'),('tiktok'),
    ('foco do produto'),('jovi x300 ultra'),('captura em alta velocidade'),('público-alvo'),('moda e lifestyle'),('stories')
), original_gaps as (
  select t.* from rt t join original_gap_titles g on g.title=t.normalized_title
), latest as (
  select * from (
    select ir.id,ir.analyzer_type,ir.status,ir.pipeline_version,ir.schema_version,ir.created_at,ir.metadata,
           row_number() over(partition by ir.analyzer_type order by ir.created_at desc,ir.id desc) rn
    from public.intelligence_runs ir join project_entity pe on pe.entity_id=ir.scope_entity_id
    where ir.analyzer_type in ('project_requirement_reconciliation','project_domain_reconciliation','project_core_semantic_domains','cross_source_linker')
  ) x where rn=1
), a_snapshot as (
  select s.* from public.project_domain_reconciliation_status s join tp on tp.project_id=s.project_id
), b_snapshot as (
  select s.* from public.project_core_semantic_status s join tp on tp.project_id=s.project_id
), regression as (
  select
    (select count(*)::integer from public.project_solution_instances psi join tp on tp.project_id=psi.project_id) solutions,
    (select count(*)::integer from public.project_solution_occurrences pso join tp on tp.project_id=pso.project_id where pso.lifecycle_status='active') solution_occurrences,
    (select count(*)::integer from public.memory_briefing_requirements mbr join tp on tp.project_id=mbr.project_id) legacy_requirements
), checks as (
  select jsonb_build_object(
    'project_found',exists(select 1 from tp),
    'resolved_by_both_golden_sources',coalesce((select proposal_matches>0 and briefing_matches>0 from target_project),false),
    'migration_is_legacy_shadow',coalesce((select migration_mode='legacy_shadow' from rs),false),
    'c02_schema_visible',coalesce((select domain_schema_version='28.7.2c0.2' from rs),false),
    'c02_run_completed',exists(select 1 from latest where analyzer_type='project_requirement_reconciliation' and status='completed' and pipeline_version='V28.7.2C0.2'),
    'legacy_rows_preserved',(select legacy_requirements=63 from regression),
    'all_legacy_rows_passed_semantic_gate',coalesce((select legacy_recall_observations=legacy_requirement_rows from rs),false),
    'evidence_first_route_exercised',coalesce((select evidence_first_observations>0 from rs),false),
    'all_current_observations_have_current_evidence',not exists(select 1 from obs where coalesce(evidence_is_current,false)=false),
    'all_active_occurrences_have_current_evidence',not exists(select 1 from occ where coalesce(evidence_is_current,false)=false),
    'no_open_requirement_observations',coalesce((select observations_open=0 from rs),false),
    'no_unexplained_legacy_shadow',coalesce((select unexplained_legacy_shadow=0 from rs),false),
    'original_13_rows_still_preserved',(select count(*)=13 from original_gaps),
    'original_13_have_semantic_explanation',not exists(select 1 from original_gaps where legacy_explanation_role is null),
    'no_semantic_no_domain_requirement_is_verified',not exists(
      select 1 from rt
      where truth_state='verified'
        and (legacy_explanation_status='no_domain_object' or legacy_explanation_role in (
          'channel_scope','platform_scope','deliverable_scope','product_attribute','experience_attribute',
          'audience_context','strategy_context','reference_signal','solution_reference'
        ))
    ),
    'filename_reference_not_current_requirement',not exists(
      select 1 from rt where lower(title) ~ '\\.(pptx?|xlsx?|docx?|pdf)$' and truth_state in ('verified','human_confirmed')
    ),
    'evidence_first_created_requirements_have_occurrence',not exists(
      select 1 from rt t
      where t.legacy_source_id is null and coalesce(t.attributes->>'origin','') like 'evidence_led_v2872c0%'
        and t.truth_state in ('verified','human_confirmed','review_required')
        and not exists(select 1 from occ o where o.requirement_id=t.id)
    ),
    'active_c0_occurrences_are_c02',not exists(select 1 from occ where coalesce(attributes->>'normalized_by','') <> 'V28.7.2C0.2'),
    'no_existing_existing_auto_merge',coalesce((
      select coalesce((metadata->>'auto_merge_existing_requirements')::boolean,false)=false
      from latest where analyzer_type='project_requirement_reconciliation'
    ),false),
    'solutions_preserved_27',(select solutions=27 from regression),
    'solution_occurrences_preserved_47',(select solution_occurrences=47 from regression),
    'a_kernel_still_converged',coalesce((select solution_instances=27 and observations_open<=1 from a_snapshot),false),
    'b_strategy_preserved_7',coalesce((select strategy_elements=7 from b_snapshot),false),
    'b_creative_platform_preserved_1',coalesce((select creative_platforms=1 from b_snapshot),false),
    'b_creative_element_preserved_1',coalesce((select creative_elements=1 from b_snapshot),false),
    'b_experience_architecture_preserved_1',coalesce((select experience_architectures=1 from b_snapshot),false),
    'b_journey_preserved_5',coalesce((select journey_moments=5 from b_snapshot),false),
    'graph_v28_6_not_rerun_after_c02',coalesce(
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
  (select to_jsonb(s) from a_snapshot s) solution_reconciliation_status,
  (select to_jsonb(s) from b_snapshot s) core_semantic_status,
  coalesce((select jsonb_agg(jsonb_build_object(
    'title',g.title,'requirement_id',g.id,'truth_state',g.truth_state,
    'legacy_explanation_role',g.legacy_explanation_role,'legacy_explanation_status',g.legacy_explanation_status,
    'legacy_explanation_action',g.legacy_explanation_action,'legacy_explanation_evidence_id',g.legacy_explanation_evidence_id
  ) order by g.normalized_title) from original_gaps g),'[]'::jsonb) original_13_semantic_resolution,
  coalesce((select jsonb_agg(jsonb_build_object(
    'id',t.id,'title',t.title,'requirement_type',t.requirement_type,'truth_state',t.truth_state,
    'legacy_source_id',t.legacy_source_id,'origin',t.attributes->>'origin',
    'has_direct_domain_evidence',t.has_direct_domain_evidence,'has_current_occurrence',t.has_current_occurrence,
    'legacy_explanation_role',t.legacy_explanation_role,'legacy_explanation_status',t.legacy_explanation_status
  ) order by t.truth_state,lower(t.title)) from rt t),'[]'::jsonb) requirement_truth_inventory,
  coalesce((select jsonb_agg(jsonb_build_object(
    'id',so.id,'origin_route',so.attributes->>'origin_route','observed_name',so.observed_name,
    'semantic_role',so.semantic_role,'status',so.status,'resolution_action',so.resolution_action,
    'resolved_domain_id',so.resolved_domain_id,'evidence_unit_id',so.evidence_unit_id
  ) order by coalesce(so.attributes->>'origin_route',''),lower(so.observed_name)) from obs so),'[]'::jsonb) current_requirement_observations,
  coalesce((select jsonb_agg(to_jsonb(x) order by x.created_at desc) from latest x),'[]'::jsonb) latest_runs;
