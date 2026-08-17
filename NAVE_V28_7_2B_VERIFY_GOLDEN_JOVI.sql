-- NAVE by VOE · V28.7.2B — Golden JOVI X300 verification
-- READ ONLY. Project resolution is by attached source filenames, never project_name + LIMIT 1.
-- Returns one row for CSV export.

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
  from project_candidates pc join public.projects p on p.id=pc.project_id
  order by (pc.proposal_matches>0 and pc.briefing_matches>0) desc,pc.matched_files desc,p.id
  limit 1
), tp as (select id as project_id from target_project),
project_entity as (
  select ke.id as entity_id from public.knowledge_entities ke join tp on ke.domain_table='projects' and ke.domain_id=tp.project_id limit 1
),
strategy as (
  select pse.*,t.truth_state,t.has_current_evidence
  from public.project_strategy_elements pse join tp on tp.project_id=pse.project_id
  left join public.project_core_semantic_truth_status t on t.domain_table='project_strategy_elements' and t.domain_id=pse.id
  where pse.lifecycle_status='active'
),
creative as (
  select pcp.*,t.truth_state,t.has_current_evidence
  from public.project_creative_platforms pcp join tp on tp.project_id=pcp.project_id
  left join public.project_core_semantic_truth_status t on t.domain_table='project_creative_platforms' and t.domain_id=pcp.id
  where pcp.lifecycle_status='active'
),
experience as (
  select pea.*,t.truth_state,t.has_current_evidence
  from public.project_experience_architectures pea join tp on tp.project_id=pea.project_id
  left join public.project_core_semantic_truth_status t on t.domain_table='project_experience_architectures' and t.domain_id=pea.id
  where pea.lifecycle_status='active'
),
journey as (
  select pjm.*,t.truth_state,t.has_current_evidence
  from public.project_journey_moments pjm join tp on tp.project_id=pjm.project_id
  left join public.project_core_semantic_truth_status t on t.domain_table='project_journey_moments' and t.domain_id=pjm.id
  where pjm.lifecycle_status='active'
),
solutions as (
  select psi.* from public.project_solution_instances psi join tp on tp.project_id=psi.project_id
),
core_relations as (
  select kr.*,coalesce((select count(*) from public.relation_evidence re where re.relation_id=kr.id),0) as evidence_count
  from public.knowledge_relations kr join project_entity pe on pe.entity_id=kr.scope_entity_id
  where kr.status='active' and coalesce(kr.attributes->>'normalized_by','')='V28.7.2B'
),
latest_runs as (
  select * from (
    select ir.id,ir.analyzer_type,ir.created_at,ir.status,
           row_number() over(partition by ir.analyzer_type order by ir.created_at desc) as rn
    from public.intelligence_runs ir join project_entity pe on pe.entity_id=ir.scope_entity_id
    where ir.analyzer_type in ('project_core_semantic_domains','project_domain_reconciliation','cross_source_linker')
  ) x where rn=1
),
checks as (
  select jsonb_build_object(
    'project_found',exists(select 1 from tp),
    'resolved_by_both_golden_sources',coalesce((select proposal_matches>0 and briefing_matches>0 from target_project),false),
    'migration_is_legacy_shadow',coalesce((select migration_mode='legacy_shadow' from public.project_domain_migration_state m join tp on tp.project_id=m.project_id),false),
    'domain_schema_is_28_7_2b',coalesce((select domain_schema_version='28.7.2b' from public.project_domain_migration_state m join tp on tp.project_id=m.project_id),false),
    'explicit_challenge_present',exists(select 1 from strategy where strategy_type='challenge' and truth_state='verified_explicit'),
    'explicit_insight_present',exists(select 1 from strategy where strategy_type='insight' and truth_state='verified_explicit'),
    'strategic_direction_present',exists(select 1 from strategy where strategy_type='strategic_direction' and truth_state='verified_explicit'),
    'on_tour_is_creative_platform',exists(select 1 from creative where lower(name) like '%on tour%' and truth_state='verified_explicit'),
    'on_tour_is_not_solution',not exists(select 1 from solutions where lower(name) like '%on tour%'),
    'event_journey_architecture_present',exists(select 1 from experience where lower(name)='event journey' and truth_state='verified_explicit'),
    'event_journey_is_not_solution',not exists(select 1 from solutions where lower(name)='event journey'),
    'pre_event_moment_present',exists(select 1 from journey where moment_type='pre_event' and truth_state='verified_explicit'),
    'event_moment_present',exists(select 1 from journey where moment_type='event' and truth_state='verified_explicit'),
    'post_event_moment_present',exists(select 1 from journey where moment_type='post_event' and truth_state='verified_explicit'),
    'product_reveal_present',exists(select 1 from journey where moment_type='product_reveal' and truth_state='verified_explicit'),
    'activation_reveal_present',exists(select 1 from journey where moment_type='activation_reveal' and truth_state='verified_explicit'),
    'platform_solutions_remain_distinct',
      exists(select 1 from solutions where lower(name) like '%youtube%')
      and exists(select 1 from solutions where lower(name) like '%instagram%')
      and exists(select 1 from solutions where lower(name) like '%tiktok%')
      and exists(select 1 from solutions where lower(name) like '%kwai%'),
    'journey_contains_relations_grounded',(select count(*) from core_relations where relation_type='contains' and evidence_count>0)>=3,
    'no_unsupported_core_truth',not exists(
      select 1 from public.project_core_semantic_truth_status t join tp on tp.project_id=t.project_id
      where t.truth_state in ('unsupported','review_required')
    ),
    'no_analyst_inference_materialized',not exists(
      select 1 from public.semantic_observations so join tp on tp.project_id=so.project_id
      where so.assertion_mode='analyst_inference' and so.status='reconciled'
        and so.resolved_domain_table in ('project_strategy_elements','project_creative_platforms','project_creative_elements','project_experience_architectures','project_journey_moments')
    ),
    'graph_v28_6_not_rerun_after_core',coalesce(
      (select max(created_at) from latest_runs where analyzer_type='cross_source_linker') <
      (select max(created_at) from latest_runs where analyzer_type='project_core_semantic_domains'),true
    )
  ) as result
)
select
  (select to_jsonb(p) from target_project p) as project,
  (select to_jsonb(s) from public.project_core_semantic_status s join tp on tp.project_id=s.project_id) as core_status,
  (select result from checks) as gate_checks,
  coalesce((select jsonb_agg(to_jsonb(x) order by x.strategy_type,lower(x.title)) from strategy x),'[]'::jsonb) as strategy_elements,
  coalesce((select jsonb_agg(to_jsonb(x) order by lower(x.name)) from creative x),'[]'::jsonb) as creative_platforms,
  coalesce((select jsonb_agg(to_jsonb(x) order by lower(x.name)) from experience x),'[]'::jsonb) as experience_architectures,
  coalesce((select jsonb_agg(to_jsonb(x) order by x.sequence_index nulls last,lower(x.title)) from journey x),'[]'::jsonb) as journey_moments,
  coalesce((select jsonb_agg(jsonb_build_object('id',id,'name',name,'solution_kind',solution_kind) order by lower(name)) from solutions),'[]'::jsonb) as solutions,
  coalesce((select jsonb_agg(to_jsonb(x) order by x.relation_type,x.relation_kind) from core_relations x),'[]'::jsonb) as core_relations,
  coalesce((select jsonb_agg(to_jsonb(x) order by x.created_at desc) from latest_runs x),'[]'::jsonb) as latest_runs;
