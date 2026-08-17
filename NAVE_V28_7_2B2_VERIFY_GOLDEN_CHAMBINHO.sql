-- NAVE by VOE · V28.7.2B2 — Golden Chambinho precision verification
-- READ ONLY. Returns one row for CSV export.

with target_project as (
  select p.*
  from public.projects p
  where p.id='0d9f1608-4bf7-4fd0-81ab-f303fdb0c136'::uuid
  limit 1
), tp as (select id as project_id from target_project),
project_entity as (
  select ke.id as entity_id from public.knowledge_entities ke join tp on ke.domain_table='projects' and ke.domain_id=tp.project_id limit 1
),
expected_strategy(strategy_type,title) as (
  values
    ('territory','NOSTALGIA'),
    ('strategic_principle','CONEXÃO'),
    ('strategic_principle','MEMÓRIA AFETIVA'),
    ('strategic_principle','PRESENÇA E ATENÇÃO'),
    ('pillar','Resgate da infância'),
    ('pillar','Conexão familiar entre pais e filhos'),
    ('pillar','Imaginação e memórias'),
    ('pillar','Coração')
),
strategy as (
  select pse.*, t.truth_state, t.has_current_evidence
  from public.project_strategy_elements pse
  join tp on tp.project_id=pse.project_id
  left join public.project_core_semantic_truth_status t on t.domain_table='project_strategy_elements' and t.domain_id=pse.id
  where pse.lifecycle_status='active'
),
creative as (
  select pcp.*, t.truth_state, t.has_current_evidence
  from public.project_creative_platforms pcp
  join tp on tp.project_id=pcp.project_id
  left join public.project_core_semantic_truth_status t on t.domain_table='project_creative_platforms' and t.domain_id=pcp.id
  where pcp.lifecycle_status='active'
),
creative_elements as (
  select pce.*, t.truth_state, t.has_current_evidence
  from public.project_creative_elements pce
  join tp on tp.project_id=pce.project_id
  left join public.project_core_semantic_truth_status t on t.domain_table='project_creative_elements' and t.domain_id=pce.id
  where pce.lifecycle_status='active'
),
experience as (
  select pea.*, t.truth_state, t.has_current_evidence
  from public.project_experience_architectures pea
  join tp on tp.project_id=pea.project_id
  left join public.project_core_semantic_truth_status t on t.domain_table='project_experience_architectures' and t.domain_id=pea.id
  where pea.lifecycle_status='active'
),
journey as (
  select pjm.*, t.truth_state, t.has_current_evidence, eu.content_text as evidence_text
  from public.project_journey_moments pjm
  join tp on tp.project_id=pjm.project_id
  left join public.project_core_semantic_truth_status t on t.domain_table='project_journey_moments' and t.domain_id=pjm.id
  left join public.evidence_units eu on eu.id=pjm.source_evidence_id
  where pjm.lifecycle_status='active'
),
core_relations as (
  select kr.*, coalesce((select count(*) from public.relation_evidence re where re.relation_id=kr.id),0) as evidence_count
  from public.knowledge_relations kr
  join project_entity pe on pe.entity_id=kr.scope_entity_id
  where kr.status='active' and coalesce(kr.attributes->>'normalized_by','')='V28.7.2B'
),
solution_summary as (
  select count(*)::integer as solutions
  from public.project_solution_instances psi join tp on tp.project_id=psi.project_id
),
execution_truth as (
  select count(*)::integer as executions
  from public.entity_current_outcomes eco
  join public.project_solution_instances psi on psi.entity_id=eco.entity_id
  join tp on tp.project_id=psi.project_id
  where eco.outcome_type='execution_status' and eco.outcome_status='executed'
),
coverage as (
  select count(*)::integer as open_gaps
  from public.intelligence_findings f
  join project_entity pe on pe.entity_id=f.scope_entity_id
  where f.status='active' and f.analyzer_type='domain_coverage_audit'
),
finance as (
  select count(*)::integer as lines,
         count(distinct fli.source_evidence_id) filter(where fli.source_evidence_id is not null)::integer as distinct_evidence_units,
         round(coalesce(sum(fli.total_value),0)::numeric,2) as total_value
  from public.financial_line_items fli join tp on tp.project_id=fli.project_id
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
    'migration_is_legacy_shadow',coalesce((select migration_mode='legacy_shadow' from public.project_domain_migration_state m join tp on tp.project_id=m.project_id),false),
    'domain_schema_is_28_7_2b',coalesce((select domain_schema_version='28.7.2b' from public.project_domain_migration_state m join tp on tp.project_id=m.project_id),false),
    'solutions_preserved_19',(select solutions=19 from solution_summary),
    'executions_preserved_8',(select executions=8 from execution_truth),
    'coverage_remains_zero',(select open_gaps=0 from coverage),
    'territory_nostalgia_verified',exists(
      select 1 from strategy where strategy_type='territory' and lower(title)='nostalgia' and truth_state='verified_explicit'
    ),
    'starting_point_memoria_afetiva_verified',exists(
      select 1 from strategy where strategy_type='strategic_principle' and lower(title) like '%memória afetiva%' and truth_state='verified_explicit'
    ),
    'starting_point_conexao_verified',exists(
      select 1 from strategy where strategy_type='strategic_principle' and lower(title)='conexão' and truth_state='verified_explicit'
    ),
    'starting_point_presenca_atencao_verified',exists(
      select 1 from strategy where strategy_type='strategic_principle' and lower(title) like '%presença%atenção%' and truth_state='verified_explicit'
    ),
    'strategy_expected_count_8',(select count(*)=8 from strategy),
    'strategy_exact_expected_set',(
      not exists (
        select 1 from expected_strategy e
        where not exists (
          select 1 from strategy s
          where s.strategy_type=e.strategy_type and lower(s.title)=lower(e.title)
        )
      )
      and not exists (
        select 1 from strategy s
        where not exists (
          select 1 from expected_strategy e
          where e.strategy_type=s.strategy_type and lower(e.title)=lower(s.title)
        )
      )
    ),
    'no_resource_metadata_as_strategy',not exists(
      select 1 from strategy s
      where coalesce(s.statement,'') ~* '(https?://|www\.)'
         or lower(s.title) ~ '^(canais? oficiais?|channels?|site( |$)|website( |$)|youtube( |$)|instagram( |$)|tiktok( |$)|linkedin( |$)|facebook( |$)|twitter( |$))'
    ),
    'starting_points_have_atomic_statements',coalesce((
      select count(*)=3
         and bool_and(
           length(trim(coalesce(statement,''))) between 8 and 450
           and lower(coalesce(statement,'')) not like '%pontos de partida%'
         )
      from strategy
      where strategy_type='strategic_principle'
        and lower(title) in ('conexão','memória afetiva','presença e atenção')
    ),false),
    'creative_platform_nostalgic_house_verified',exists(
      select 1 from creative where lower(name) like '%casa%nostalg%' and truth_state='verified_explicit'
    ),
    'pov_is_creative_not_strategy',
      exists(select 1 from creative_elements where creative_type='pov' and lower(title) like '%casa%nostalg%')
      and not exists(select 1 from strategy where lower(title) like '%casa%nostalg%'),
    'no_unsupported_core_truth',not exists(
      select 1 from public.project_core_semantic_truth_status t join tp on tp.project_id=t.project_id
      where t.truth_state in ('unsupported','review_required')
    ),
    'no_analyst_inference_materialized',not exists(
      select 1 from public.semantic_observations so join tp on tp.project_id=so.project_id
      where so.assertion_mode='analyst_inference' and so.resolved_domain_table in (
        'project_strategy_elements','project_creative_platforms','project_creative_elements','project_experience_architectures','project_journey_moments'
      ) and so.status='reconciled'
    ),
    'journey_never_fabricated_without_explicit_source',not exists(
      select 1 from journey j
      where j.truth_state='verified_explicit'
        and lower(coalesce(j.evidence_text,'')) not like '%journey%'
        and lower(coalesce(j.evidence_text,'')) not like '%jornada%'
        and lower(coalesce(j.evidence_text,'')) not like '%reveal%'
        and lower(coalesce(j.evidence_text,'')) not like '%revel%'
    ),
    'strategy_creative_relation_is_typed_and_grounded',exists(
      select 1 from core_relations r
      where r.relation_type='expressed_by' and r.relation_kind in ('fact','inference') and r.evidence_count>0
    ),
    'finance_54_lines',(select lines=54 from finance),
    'finance_54_distinct_evidence_units',(select distinct_evidence_units=54 from finance),
    'finance_total_554310_85',(select total_value=554310.85 from finance),
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
  coalesce((
    select jsonb_agg(to_jsonb(x) order by x.updated_at desc, lower(x.title))
    from public.project_strategy_elements x
    join tp on tp.project_id=x.project_id
    where x.lifecycle_status='invalidated'
      and coalesce(x.attributes->>'invalidated_by','')='V28.7.2B2'
  ),'[]'::jsonb) as b2_invalidated_strategy_history,
  coalesce((select jsonb_agg(to_jsonb(x) order by lower(x.name)) from creative x),'[]'::jsonb) as creative_platforms,
  coalesce((select jsonb_agg(to_jsonb(x) order by x.creative_type,lower(x.title)) from creative_elements x),'[]'::jsonb) as creative_elements,
  coalesce((select jsonb_agg(to_jsonb(x) order by lower(x.name)) from experience x),'[]'::jsonb) as experience_architectures,
  coalesce((select jsonb_agg(to_jsonb(x) order by x.sequence_index nulls last,lower(x.title)) from journey x),'[]'::jsonb) as journey_moments,
  coalesce((select jsonb_agg(to_jsonb(x) order by x.relation_type,x.relation_kind) from core_relations x),'[]'::jsonb) as core_relations,
  (select to_jsonb(f) from finance f) as finance,
  coalesce((select jsonb_agg(to_jsonb(x) order by x.created_at desc) from latest_runs x),'[]'::jsonb) as latest_runs;
