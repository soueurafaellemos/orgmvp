-- NAVE by VOE · V28.7.2C0 — Golden JOVI Requirement reconciliation verification
-- READ ONLY. Returns one row for CSV export.
-- Project resolution uses the two Golden source filenames, never display name alone.

with project_candidates as (
  select pf.project_id,
         count(*) filter(where lower(coalesce(pf.file_name,'')) like '%lancamento_jovi_x300%') as proposal_matches,
         count(*) filter(where lower(coalesce(pf.file_name,'')) like '%briefing_jovi_x300%') as briefing_matches,
         count(*) as matched_files
  from public.project_files pf
  where lower(coalesce(pf.file_name,'')) like '%lancamento_jovi_x300%'
     or lower(coalesce(pf.file_name,'')) like '%briefing_jovi_x300%'
  group by pf.project_id
), target_project as (
  select p.*,pc.proposal_matches,pc.briefing_matches,pc.matched_files
  from project_candidates pc
  join public.projects p on p.id=pc.project_id
  order by (pc.proposal_matches>0 and pc.briefing_matches>0) desc,pc.matched_files desc,p.id
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
  select t.*,
         regexp_replace(lower(trim(t.title)),'[;:]+$','','g') as normalized_title
  from public.project_requirement_truth_status t
  join tp on tp.project_id=t.project_id
), golden_gap_titles(title) as (
  values
    ('criadores de conteúdo'),('filmmakers'),('fotógrafos'),('kwai'),('instagram'),('youtube'),('tiktok'),
    ('foco do produto'),('jovi x300 ultra'),('captura em alta velocidade'),('público-alvo'),('moda e lifestyle'),('stories')
), golden_gap_rows as (
  select t.*
  from requirement_truth t
  join golden_gap_titles g on g.title=t.normalized_title
), c0_observations as (
  select so.*,eu.is_current as evidence_is_current
  from public.semantic_observations so
  join tp on tp.project_id=so.project_id
  left join public.evidence_units eu on eu.id=so.evidence_unit_id
  where so.domain_hint='requirement' and so.status <> 'superseded'
), c0_created_requirements as (
  select pr.*
  from public.project_requirements pr
  join tp on tp.project_id=pr.project_id
  where coalesce(pr.attributes->>'origin','')='evidence_led_v2872c0'
), latest_runs as (
  select * from (
    select ir.id,ir.analyzer_type,ir.status,ir.created_at,ir.metadata,
           row_number() over(partition by ir.analyzer_type order by ir.created_at desc,ir.id desc) as rn
    from public.intelligence_runs ir
    join project_entity pe on pe.entity_id=ir.scope_entity_id
    where ir.analyzer_type in ('project_requirement_reconciliation','project_domain_reconciliation','project_core_semantic_domains','cross_source_linker')
  ) x where rn=1
), a_snapshot as (
  select s.* from public.project_domain_reconciliation_status s join tp on tp.project_id=s.project_id
), b_snapshot as (
  select s.* from public.project_core_semantic_status s join tp on tp.project_id=s.project_id
), domain_snapshot as (
  select
    (select count(*)::integer from public.project_solution_instances psi join tp on tp.project_id=psi.project_id) as solutions,
    (select count(*)::integer from public.project_solution_occurrences pso join tp on tp.project_id=pso.project_id where pso.lifecycle_status='active') as solution_occurrences,
    (select count(*)::integer from public.memory_briefing_requirements mbr join tp on tp.project_id=mbr.project_id) as legacy_requirements
), checks as (
  select jsonb_build_object(
    'project_found',exists(select 1 from tp),
    'resolved_by_both_golden_sources',coalesce((select proposal_matches>0 and briefing_matches>0 from target_project),false),
    'migration_is_legacy_shadow',coalesce((select migration_mode='legacy_shadow' from requirement_status),false),
    'c0_schema_visible',coalesce((select domain_schema_version='28.7.2c0' from requirement_status),false),
    'c0_run_completed',exists(select 1 from latest_runs where analyzer_type='project_requirement_reconciliation' and status='completed'),
    'all_c0_observations_have_current_evidence',not exists(select 1 from c0_observations where coalesce(evidence_is_current,false)=false),
    'all_thirteen_original_gaps_still_accounted_for',(select count(*)=13 from golden_gap_rows),
    'all_thirteen_original_gaps_explained_or_verified',not exists(
      select 1 from golden_gap_rows
      where truth_state not in ('verified','human_confirmed','review_required')
        and legacy_explanation_role is null
    ),
    'no_unexplained_legacy_shadow',coalesce((select unexplained_legacy_shadow=0 from requirement_status),false),
    'classified_non_requirement_signals_exist',coalesce((
      select classified_scope+classified_attribute+classified_context>0 from requirement_status
    ),false),
    'new_c0_requirements_have_current_evidence',not exists(
      select 1 from c0_created_requirements pr
      where not exists(
        select 1 from public.domain_object_evidence doe
        join public.evidence_units eu on eu.id=doe.evidence_unit_id and eu.is_current=true
        where doe.domain_table='project_requirements' and doe.domain_id=pr.id
      )
    ),
    'c0_never_auto_merges_existing_requirements',coalesce((
      select coalesce((metadata->>'auto_merge_existing_requirements')::boolean,false)=false
      from latest_runs where analyzer_type='project_requirement_reconciliation'
    ),false),
    'solutions_preserved_27',(select solutions=27 from domain_snapshot),
    'solution_occurrences_preserved_47',(select solution_occurrences=47 from domain_snapshot),
    'legacy_requirement_rows_preserved',(select legacy_requirements=63 from domain_snapshot),
    'a_kernel_still_converged',coalesce((
      select solution_instances=27 and observations_open<=1
      from a_snapshot
    ),false),
    'b_strategy_preserved_7',coalesce((select strategy_elements=7 from b_snapshot),false),
    'b_creative_platform_preserved_1',coalesce((select creative_platforms=1 from b_snapshot),false),
    'b_creative_element_preserved_1',coalesce((select creative_elements=1 from b_snapshot),false),
    'b_experience_architecture_preserved_1',coalesce((select experience_architectures=1 from b_snapshot),false),
    'b_journey_preserved_5',coalesce((select journey_moments=5 from b_snapshot),false),
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
  (select to_jsonb(s) from a_snapshot s) as solution_reconciliation_status,
  (select to_jsonb(s) from b_snapshot s) as core_semantic_status,
  coalesce((
    select jsonb_agg(jsonb_build_object(
      'title',g.title,
      'requirement_id',g.id,
      'truth_state',g.truth_state,
      'has_current_evidence',g.has_current_evidence,
      'legacy_explanation_role',g.legacy_explanation_role,
      'legacy_explanation_status',g.legacy_explanation_status,
      'legacy_explanation_action',g.legacy_explanation_action,
      'legacy_explanation_evidence_id',g.legacy_explanation_evidence_id
    ) order by g.normalized_title)
    from golden_gap_rows g
  ),'[]'::jsonb) as original_13_gap_resolution,
  coalesce((
    select jsonb_agg(jsonb_build_object(
      'observed_name',so.observed_name,
      'semantic_role',so.semantic_role,
      'status',so.status,
      'resolution_action',so.resolution_action,
      'resolved_domain_id',so.resolved_domain_id,
      'evidence_unit_id',so.evidence_unit_id,
      'evidence_is_current',so.evidence_is_current
    ) order by lower(so.observed_name))
    from c0_observations so
  ),'[]'::jsonb) as c0_observations,
  coalesce((select jsonb_agg(to_jsonb(x) order by x.created_at desc) from latest_runs x),'[]'::jsonb) as latest_runs;
