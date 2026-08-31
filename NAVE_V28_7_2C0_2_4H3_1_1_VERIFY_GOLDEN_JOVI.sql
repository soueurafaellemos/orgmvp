-- NAVE by VOE · V28.7.2C0.2.4H3.1.1
-- Golden JOVI — Cross-Unit Structural Context + Golden Verifier Repair
-- READ ONLY. Não altera nenhuma tabela.
--
-- Rodar somente DEPOIS de executar uma vez:
-- "Requirement Truth Repair · V28.7.2C0.2.4H3.1.1"
-- no projeto JOVI X300.
--
-- H3.1.1 corrige dois falsos verdes possíveis do H3:
-- 1) bullets isolados em Evidence Units próprias passam a herdar o parent estrutural
--    imediatamente anterior (audience/platform/example/etc.);
-- 2) títulos de regressão são comparados após remover pontuação terminal, portanto
--    "Storytelling detalhado." não escapa de "storytelling detalhado".

with project_candidates as (
  select
    pf.project_id,
    count(*) filter (where lower(coalesce(pf.file_name,'')) like '%briefing_jovi_x300%') as briefing_matches,
    count(*) filter (where lower(coalesce(pf.file_name,'')) like '%lancamento_jovi_x300%') as proposal_matches,
    count(*) as matched_files
  from public.project_files pf
  where lower(coalesce(pf.file_name,'')) like '%briefing_jovi_x300%'
     or lower(coalesce(pf.file_name,'')) like '%lancamento_jovi_x300%'
  group by pf.project_id
),
target_project as (
  select p.*, pc.briefing_matches, pc.proposal_matches, pc.matched_files
  from project_candidates pc
  join public.projects p on p.id=pc.project_id
  order by (pc.briefing_matches > 0 and pc.proposal_matches > 0) desc, pc.matched_files desc, p.id
  limit 1
),
tp as (select id as project_id from target_project),
project_entity as (
  select ke.id as entity_id
  from public.knowledge_entities ke
  join tp on ke.domain_table='projects' and ke.domain_id=tp.project_id
  limit 1
),
rs as (
  select s.* from public.project_requirement_reconciliation_status s join tp on tp.project_id=s.project_id
),
rt as (
  select
    t.*,
    regexp_replace(
      lower(trim(coalesce(t.title,''))),
      '[[:space:][:punct:]]+$',
      '',
      'g'
    ) as normalized_terminal_title
  from public.project_requirement_truth_status t
  join tp on tp.project_id=t.project_id
),
obs as (
  select
    so.*,
    eu.is_current as evidence_is_current,
    regexp_replace(
      lower(trim(coalesce(so.observed_name,''))),
      '[[:space:][:punct:]]+$',
      '',
      'g'
    ) as normalized_terminal_name
  from public.semantic_observations so
  join tp on tp.project_id=so.project_id
  left join public.evidence_units eu on eu.id=so.evidence_unit_id
  where so.domain_hint='requirement' and so.status <> 'superseded'
),
occ as (
  select pro.*, eu.is_current as evidence_is_current
  from public.project_requirement_occurrences pro
  join tp on tp.project_id=pro.project_id
  left join public.evidence_units eu on eu.id=pro.evidence_unit_id
  where pro.lifecycle_status='active'
),
latest as (
  select * from (
    select ir.*, row_number() over(partition by ir.analyzer_type order by ir.created_at desc, ir.id desc) rn
    from public.intelligence_runs ir
    join project_entity pe on pe.entity_id=ir.scope_entity_id
    where ir.analyzer_type in (
      'project_requirement_reconciliation',
      'project_domain_reconciliation',
      'project_core_semantic_domains',
      'cross_source_linker'
    )
  ) q where rn=1
),
req_run as (
  select * from latest where analyzer_type='project_requirement_reconciliation'
),
a_run as (
  select * from latest where analyzer_type='project_domain_reconciliation'
),
b_run as (
  select * from latest where analyzer_type='project_core_semantic_domains'
),
a_snapshot as (
  select s.* from public.project_domain_reconciliation_status s join tp on tp.project_id=s.project_id
),
b_snapshot as (
  select s.* from public.project_core_semantic_status s join tp on tp.project_id=s.project_id
),
regression as (
  select
    (select count(*)::integer from public.project_solution_instances psi join tp on tp.project_id=psi.project_id) as solutions,
    (select count(*)::integer from public.project_solution_occurrences pso join tp on tp.project_id=pso.project_id where pso.lifecycle_status='active') as solution_occurrences,
    (select count(*)::integer from public.memory_briefing_requirements mbr join tp on tp.project_id=mbr.project_id) as legacy_requirements
),
forbidden_verified as (
  select t.*
  from rt t
  where t.truth_state in ('verified','human_confirmed')
    and (
      t.normalized_terminal_title in (
        'jovi x300 ultra',
        'frequentadores de festivais de música',
        'frequentadores de festivais de musica',
        'universo da moda e lifestyle',
        'storytelling detalhado',
        'mini show ao vivo',
        'performance com muito movimento'
      )
      or (
        lower(t.title) like '%presskit%'
        and (
          lower(coalesce(t.description,'')) like '%não nos confirmou%'
          or lower(coalesce(t.description,'')) like '%nao nos confirmou%'
          or lower(coalesce(t.description,'')) like '%vale sugerirmos%'
        )
      )
    )
),
structural_targets as (
  select *
  from obs
  where coalesce(attributes->>'origin_route','')='legacy_recall'
    and normalized_terminal_name in (
      'frequentadores de festivais de música',
      'frequentadores de festivais de musica',
      'universo da moda e lifestyle',
      'storytelling detalhado',
      'mini show ao vivo',
      'performance com muito movimento'
    )
),
mc_obs as (
  select * from obs
  where coalesce(attributes->>'origin_route','')='evidence_first'
    and lower(observed_name) ~ '(não|nao).*(necess[aá]rio).*or[cç]armos.*(mc|mestre de cerim)'
  order by updated_at desc nulls last, id desc limit 1
),
timing_obs as (
  select * from obs
  where coalesce(attributes->>'origin_route','')='evidence_first'
    and lower(observed_name) ~ '(necess[aá]rio).*(desenhar|desenharmos|sugerir|sugerirmos).*(timing|timming|apresenta[cç][aã]o)'
  order by updated_at desc nulls last, id desc limit 1
),
checks as (
  select jsonb_build_object(
    'project_found', exists(select 1 from tp),
    'resolved_by_both_golden_sources', coalesce((select briefing_matches>0 and proposal_matches>0 from target_project),false),
    'migration_is_legacy_shadow', coalesce((select migration_mode='legacy_shadow' from rs),false),
    'c024_schema_visible', coalesce((select domain_schema_version='28.7.2c0.2.4' from rs),false),
    'c024h31_run_completed', exists(
      select 1 from req_run
      where status='completed'
        and pipeline_version='V28.7.2C0.2.4H3.1.1'
    ),

    'semantic_gate_pass', coalesce((select semantic_gate_pass from rs),false),
    'semantic_gate_has_zero_blockers', coalesce((select semantic_gate_blockers=0 from rs),false),
    'no_open_requirement_observations', coalesce((select observations_open=0 from rs),false),
    'no_observation_review_required', coalesce((select observations_review_required=0 from rs),false),
    'no_identity_review_required', coalesce((select review_required=0 from rs),false),
    'no_conflicted_requirement_identity', coalesce((select conflicted=0 from rs),false),
    'no_unexplained_legacy_shadow', coalesce((select unexplained_legacy_shadow=0 from rs),false),

    'legacy_rows_preserved', coalesce((select legacy_requirement_rows=(select legacy_requirements from regression) from rs),false),
    'all_current_observations_have_current_evidence', not exists(select 1 from obs where coalesce(evidence_is_current,false)=false),
    'all_active_occurrences_have_current_evidence', not exists(select 1 from occ where coalesce(evidence_is_current,false)=false),

    -- Critical H3.1.1 precision checks. Terminal punctuation is normalized first.
    'product_audience_platform_examples_not_current_requirements', not exists(select 1 from forbidden_verified),
    'cross_unit_audience_festival_is_no_domain', exists(
      select 1 from structural_targets
      where normalized_terminal_name in (
        'frequentadores de festivais de música',
        'frequentadores de festivais de musica'
      )
        and semantic_role='audience_context'
        and status='no_domain_object'
        and resolution_action='preserve_context'
    ),
    'cross_unit_audience_lifestyle_is_no_domain', exists(
      select 1 from structural_targets
      where normalized_terminal_name='universo da moda e lifestyle'
        and semantic_role='audience_context'
        and status='no_domain_object'
        and resolution_action='preserve_context'
    ),
    'cross_unit_storytelling_is_platform_scope', exists(
      select 1 from structural_targets
      where normalized_terminal_name='storytelling detalhado'
        and semantic_role='platform_scope'
        and status='no_domain_object'
        and resolution_action='attach_scope'
    ),
    'cross_unit_mini_show_is_example', exists(
      select 1 from structural_targets
      where normalized_terminal_name='mini show ao vivo'
        and semantic_role='example_signal'
        and status='no_domain_object'
        and resolution_action='preserve_example'
    ),
    'cross_unit_movement_performance_is_example', exists(
      select 1 from structural_targets
      where normalized_terminal_name='performance com muito movimento'
        and semantic_role='example_signal'
        and status='no_domain_object'
        and resolution_action='preserve_example'
    ),

    'suggestion_role_exercised', coalesce((select classified_suggestion>0 from rs),false),
    'example_role_exercised', coalesce((select classified_example>0 from rs),false),
    'role_only_objects_are_no_domain', not exists(
      select 1 from obs
      where semantic_role in ('suggestion_signal','example_signal','parameter_signal','constraint_qualifier')
        and status <> 'no_domain_object'
    ),
    'semantic_no_domain_legacy_identity_not_verified', not exists(
      select 1 from rt
      where truth_state in ('verified','human_confirmed')
        and legacy_explanation_role in (
          'channel_scope','platform_scope','deliverable_scope','product_attribute','experience_attribute',
          'audience_context','strategy_context','reference_signal','solution_reference','form_prompt',
          'suggestion_signal','example_signal','parameter_signal','constraint_qualifier'
        )
    ),

    'mc_exclusion_and_timing_are_separate_requirement_identities', coalesce((
      select
        m.resolved_domain_id is not null
        and t.resolved_domain_id is not null
        and m.resolved_domain_id <> t.resolved_domain_id
      from mc_obs m cross join timing_obs t
    ),false),
    'mc_exclusion_is_requirement', coalesce((
      select semantic_role='requirement_candidate' and status='reconciled' and resolved_domain_id is not null
      from mc_obs
    ),false),
    'mandatory_timing_is_requirement', coalesce((
      select semantic_role='requirement_candidate' and status='reconciled' and resolved_domain_id is not null
      from timing_obs
    ),false),
    'jovi_product_model_not_current_requirement', not exists(
      select 1 from rt
      where truth_state in ('verified','human_confirmed')
        and normalized_terminal_title='jovi x300 ultra'
    ),
    'jovi_bare_model_legacy_recall_is_no_domain', exists(
      select 1 from obs
      where coalesce(attributes->>'origin_route','')='legacy_recall'
        and normalized_terminal_name='jovi x300 ultra'
        and semantic_role='product_attribute'
        and status='no_domain_object'
    ),
    'hands_on_lab_not_bound_to_bare_product_identity', not exists(
      select 1
      from obs o
      join public.project_requirements pr on pr.id=o.resolved_domain_id
      where coalesce(o.attributes->>'origin_route','')='evidence_first'
        and lower(o.observed_name) like 'experience & hands-on lab:%'
        and regexp_replace(
              lower(trim(coalesce(pr.title,''))),
              '[[:space:][:punct:]]+$','', 'g'
            )='jovi x300 ultra'
        and o.status='reconciled'
    ),

    'no_existing_existing_auto_merge', coalesce((
      select coalesce((metadata->>'auto_merge_existing_requirements')::boolean,false)=false
      from req_run
    ),false),
    'h31_run_declares_cross_unit_context', coalesce((
      select coalesce((metadata->>'cross_unit_structural_context')::boolean,false)=true
      from req_run
    ),false),

    'a_kernel_still_converged', coalesce((select solution_instances=27 and observations_open<=1 from a_snapshot),false),
    'solutions_preserved_27', (select solutions=27 from regression),
    'solution_occurrences_preserved_47', (select solution_occurrences=47 from regression),
    'a_not_rerun_by_h31', coalesce((select a.created_at < r.created_at from a_run a cross join req_run r),true),
    'b_not_rerun_by_h31', coalesce((select b.created_at < r.created_at from b_run b cross join req_run r),true),
    'b_strategy_preserved_7', coalesce((select strategy_elements=7 from b_snapshot),false),
    'b_creative_platform_preserved_1', coalesce((select creative_platforms=1 from b_snapshot),false),
    'b_creative_element_preserved_1', coalesce((select creative_elements=1 from b_snapshot),false),
    'b_experience_architecture_preserved_1', coalesce((select experience_architectures=1 from b_snapshot),false),
    'b_journey_preserved_5', coalesce((select journey_moments=5 from b_snapshot),false),

    'graph_v28_6_not_rerun_after_c024', coalesce(
      (select created_at from latest where analyzer_type='cross_source_linker') <
      (select created_at from req_run),
      true
    )
  ) as result
)
select
  (select to_jsonb(p) from target_project p) as project,
  (select to_jsonb(s) from rs s) as requirement_status,
  (select result from checks) as gate_checks,
  (select to_jsonb(r) from regression r) as regression_snapshot,
  (select to_jsonb(s) from a_snapshot s) as solution_reconciliation_status,
  (select to_jsonb(s) from b_snapshot s) as core_semantic_status,

  coalesce((
    select jsonb_agg(jsonb_build_object(
      'title',f.title,
      'normalized_terminal_title',f.normalized_terminal_title,
      'truth_state',f.truth_state,
      'legacy_explanation_role',f.legacy_explanation_role,
      'legacy_explanation_status',f.legacy_explanation_status,
      'has_current_occurrence',f.has_current_occurrence
    ) order by lower(f.title), f.id)
    from forbidden_verified f
  ),'[]'::jsonb) as forbidden_verified_requirements,

  coalesce((
    select jsonb_agg(jsonb_build_object(
      'observed_name',o.observed_name,
      'normalized_terminal_name',o.normalized_terminal_name,
      'semantic_role',o.semantic_role,
      'status',o.status,
      'resolution_action',o.resolution_action,
      'resolved_domain_id',o.resolved_domain_id,
      'origin_route',o.attributes->>'origin_route',
      'h31_structural_context',o.attributes->>'h31_structural_context',
      'h31_structural_role',o.attributes->>'h31_structural_role',
      'evidence_unit_id',o.evidence_unit_id
    ) order by o.normalized_terminal_name, o.id)
    from structural_targets o
  ),'[]'::jsonb) as h31_cross_unit_observation_audit,

  coalesce((
    select jsonb_agg(jsonb_build_object(
      'observed_name',o.observed_name,
      'semantic_role',o.semantic_role,
      'status',o.status,
      'resolution_action',o.resolution_action,
      'resolved_domain_id',o.resolved_domain_id,
      'origin_route',o.attributes->>'origin_route',
      'evidence_unit_id',o.evidence_unit_id
    ) order by o.semantic_role, lower(o.observed_name), o.id)
    from obs o
    where o.semantic_role in ('suggestion_signal','example_signal','parameter_signal','constraint_qualifier')
       or o.id in (select id from mc_obs union select id from timing_obs)
  ),'[]'::jsonb) as precision_observation_audit,

  coalesce((
    select jsonb_agg(to_jsonb(x) order by x.created_at desc) from latest x
  ),'[]'::jsonb) as latest_runs;
