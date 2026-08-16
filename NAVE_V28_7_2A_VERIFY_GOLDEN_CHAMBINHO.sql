-- NAVE by VOE · V28.7.2A — Golden Chambinho verification
-- READ ONLY. Returns one row so Supabase can export the full diagnostic as one CSV.

with target_project as (
  select p.*
  from public.projects p
  where lower(coalesce(p.project_name,'')) = 'festivalzinho chambinho'
  limit 1
),
tp as (
  select id as project_id from target_project
),
project_entity as (
  select ke.id as entity_id
  from public.knowledge_entities ke
  join tp on ke.domain_table = 'projects' and ke.domain_id = tp.project_id
  limit 1
),
solution_rows as (
  select
    psi.id,
    psi.entity_id,
    psi.name,
    psi.solution_kind,
    psi.proposal_status,
    psi.execution_status,
    psi.legacy_source_table,
    psi.attributes,
    coalesce((
      select jsonb_agg(jsonb_build_object(
        'phase', pso.occurrence_phase,
        'role', pso.occurrence_role,
        'observed_name', pso.observed_name,
        'evidence_unit_id', pso.evidence_unit_id,
        'legacy_memory_item_id', pso.legacy_memory_item_id
      ) order by pso.created_at)
      from public.project_solution_occurrences pso
      where pso.solution_instance_id = psi.id
        and pso.lifecycle_status = 'active'
    ), '[]'::jsonb) as occurrences
  from public.project_solution_instances psi
  join tp on tp.project_id = psi.project_id
),
execution_truth as (
  select
    psi.name,
    eco.id as outcome_id,
    eco.outcome_status,
    eco.source_evidence_id,
    eo.source_observation_id,
    eots.truth_state,
    eots.provenance_method
  from public.entity_current_outcomes eco
  join public.entity_outcome_truth_status eots on eots.id = eco.id
  join public.entity_outcomes eo on eo.id = eco.id
  join public.project_solution_instances psi on psi.entity_id = eco.entity_id
  join tp on tp.project_id = psi.project_id
  where eco.outcome_type = 'execution_status'
),
commercial_truth as (
  select
    eco.outcome_type,
    eco.outcome_status,
    eots.truth_state,
    eots.provenance_method,
    eco.source_evidence_id
  from public.entity_current_outcomes eco
  join public.entity_outcome_truth_status eots on eots.id = eco.id
  join project_entity pe on pe.entity_id = eco.entity_id
  where eco.outcome_type in ('process_type','commercial_result')
),
observation_rows as (
  select
    so.id,
    so.observation_kind,
    so.observed_name,
    so.observed_type,
    so.occurrence_phase,
    so.occurrence_role,
    so.status,
    so.resolution_action,
    so.resolved_domain_id,
    so.evidence_unit_id,
    so.source_asset_id,
    so.source_authority_score,
    so.model_confidence,
    so.extraction_method,
    so.resolution_detail
  from public.semantic_observations so
  join tp on tp.project_id = so.project_id
  where so.status <> 'superseded'
),
active_findings as (
  select
    f.analyzer_type,
    f.finding_type,
    f.title,
    f.statement,
    f.confidence
  from public.intelligence_findings f
  join public.knowledge_entities pe on pe.id = f.scope_entity_id
  join tp on pe.domain_table = 'projects' and pe.domain_id = tp.project_id
  where f.status = 'active'
    and f.analyzer_type in ('domain_coverage_audit','domain_identity_audit')
),
finance as (
  select
    count(*)::integer as lines,
    count(*) filter (where fli.source_evidence_id is not null)::integer as lines_with_evidence,
    count(distinct fli.source_evidence_id) filter (where fli.source_evidence_id is not null)::integer as distinct_evidence_units,
    round(coalesce(sum(fli.total_value),0)::numeric,2) as total_value
  from public.financial_line_items fli
  join tp on tp.project_id = fli.project_id
),
latest_runs as (
  select * from (
    select
      ir.id,
      ir.analyzer_type,
      ir.status,
      ir.pipeline_version,
      ir.schema_version,
      ir.created_at,
      ir.completed_at,
      row_number() over (partition by ir.analyzer_type order by ir.created_at desc) as rn
    from public.intelligence_runs ir
    join public.knowledge_entities pe on pe.id = ir.scope_entity_id
    join tp on pe.domain_table = 'projects' and pe.domain_id = tp.project_id
    where ir.analyzer_type in (
      'project_domain_reconciliation','domain_coverage_audit','domain_identity_audit',
      'cross_source_linker','project_domain_normalization'
    )
  ) ranked where rn = 1
),
expected_execution(name) as (
  values
    ('Amarelinha'),
    ('Jogo da memória'),
    ('Pescaria'),
    ('Distribuição de Produtos'),
    ('Mascote em Tamanho Real'),
    ('Tatuagens Temporárias'),
    ('Folhas para colorir'),
    ('Oficina Origami de Coração')
),
logistics_not_solutions(name) as (
  values
    ('Polpas'),
    ('Pouchs'),
    ('Garrafinhas'),
    ('Petit Morango'),
    ('Petit Banana e Maçã'),
    ('Bola de sabão')
),
checks as (
  select jsonb_build_object(
    'project_found', exists(select 1 from tp),
    'migration_is_legacy_shadow', coalesce((select migration_mode = 'legacy_shadow' from public.project_domain_migration_state m join tp on tp.project_id=m.project_id), false),
    'domain_schema_is_28_7_2a', coalesce((select domain_schema_version = '28.7.2a' from public.project_domain_migration_state m join tp on tp.project_id=m.project_id), false),
    'solution_count', (select count(*) from solution_rows),
    'evidence_led_solution_count', (select count(*) from solution_rows where coalesce(attributes->>'origin','')='evidence_led_v2872a'),
    'verified_execution_current_count', (select count(*) from execution_truth where truth_state='verified' and outcome_status='executed'),
    'all_expected_executions_current', not exists (
      select 1 from expected_execution ee
      where not exists (
        select 1 from execution_truth et
        where lower(et.name) = lower(ee.name)
          and et.truth_state='verified'
          and et.outcome_status='executed'
      )
    ),
    'execution_truth_is_exactly_expected_set',
      (select count(*) from execution_truth where truth_state='verified' and outcome_status='executed') = 8
      and not exists (
        select 1 from execution_truth et
        where et.truth_state='verified' and et.outcome_status='executed'
          and not exists (select 1 from expected_execution ee where lower(ee.name)=lower(et.name))
      ),
    'coverage_findings_open', (select count(*) from active_findings where analyzer_type='domain_coverage_audit'),
    'coverage_gaps_reconciled', (select count(*) from active_findings where analyzer_type='domain_coverage_audit') = 0,
    'identity_findings_open', (select count(*) from active_findings where analyzer_type='domain_identity_audit'),
    'pelucia_chaveiro_remain_distinct',
      (select count(*) from solution_rows where lower(name) in (lower('Pelúcia'), lower('Chaveiro'))) = 2,
    'pelucia_chaveiro_review_signal_present', exists (
      select 1 from active_findings
      where analyzer_type='domain_identity_audit'
        and finding_type='possible_duplicate_identity'
        and lower(title) like '%pelúcia%'
        and lower(title) like '%chaveiro%'
    ),
    'logistics_false_solution_count', (
      select count(*) from solution_rows s
      where exists (select 1 from logistics_not_solutions l where lower(l.name)=lower(s.name))
    ),
    'no_logistics_promoted_to_solution', not exists (
      select 1 from solution_rows s
      where exists (select 1 from logistics_not_solutions l where lower(l.name)=lower(s.name))
    ),
    'budget_constraint_400k_scoped', exists (
      select 1 from public.project_requirement_constraints prc
      join tp on tp.project_id=prc.project_id
      where prc.status='active' and prc.constraint_type='budget'
        and prc.value_numeric=400000 and prc.currency='BRL'
        and prc.scope_type='project'
        and prc.operator in ('unspecified','=','<=','>=','envelope','other')
    ),
    'audience_range_6k_8k_scoped', exists (
      select 1 from public.project_requirement_constraints prc
      join tp on tp.project_id=prc.project_id
      where prc.status='active' and prc.constraint_type='expected_attendees'
        and prc.operator='between' and prc.value_min=6000 and prc.value_max=8000 and prc.unit='people'
        and prc.scope_type='event'
    ),
    'context_has_objective', exists (
      select 1 from public.project_context_elements pce join tp on tp.project_id=pce.project_id
      where pce.lifecycle_status='active' and pce.context_type='objective' and pce.source_evidence_id is not null
    ),
    'context_has_audience', exists (
      select 1 from public.project_context_elements pce join tp on tp.project_id=pce.project_id
      where pce.lifecycle_status='active' and pce.context_type='audience_context' and pce.source_evidence_id is not null
    ),
    'commercial_process_direct_current', exists (
      select 1 from commercial_truth
      where outcome_type='process_type' and outcome_status='direct' and truth_state='verified'
    ),
    'commercial_not_applicable_current', exists (
      select 1 from commercial_truth
      where outcome_type='commercial_result' and outcome_status='not_applicable' and truth_state='verified'
    ),
    'legacy_unverified_never_current', not exists (
      select 1
      from public.entity_current_outcomes eco
      join public.entity_outcome_truth_status eots on eots.id=eco.id
      join tp on tp.project_id=eco.project_id
      where eots.truth_state='legacy_unverified'
    ),
    'finance_54_lines', (select lines=54 from finance),
    'finance_54_distinct_evidence_units', (select distinct_evidence_units=54 from finance),
    'finance_total_554310_85', (select total_value=554310.85 from finance),
    'graph_v28_6_not_rerun_after_reconciliation', coalesce(
      (select max(created_at) from latest_runs where analyzer_type='cross_source_linker')
      <
      (select max(created_at) from latest_runs where analyzer_type='project_domain_reconciliation'),
      true
    )
  ) as result
)
select
  (select to_jsonb(p) from target_project p) as project,
  (select to_jsonb(r) from public.project_domain_reconciliation_status r join tp on tp.project_id=r.project_id) as reconciliation_status,
  (select result from checks) as gate_checks,
  coalesce((select jsonb_agg(to_jsonb(s) order by lower(s.name)) from solution_rows s), '[]'::jsonb) as solutions,
  coalesce((select jsonb_agg(to_jsonb(e) order by lower(e.name)) from execution_truth e), '[]'::jsonb) as current_execution_truth,
  coalesce((select jsonb_agg(to_jsonb(c) order by c.outcome_type) from commercial_truth c), '[]'::jsonb) as current_commercial_truth,
  coalesce((select jsonb_agg(to_jsonb(o) order by o.observation_kind, lower(o.observed_name)) from observation_rows o), '[]'::jsonb) as semantic_observations,
  coalesce((
    select jsonb_agg(to_jsonb(pce) order by pce.context_type, pce.title)
    from public.project_context_elements pce join tp on tp.project_id=pce.project_id
    where pce.lifecycle_status='active'
  ), '[]'::jsonb) as context_elements,
  coalesce((
    select jsonb_agg(to_jsonb(prc) order by prc.constraint_type, prc.created_at)
    from public.project_requirement_constraints prc join tp on tp.project_id=prc.project_id
    where prc.status='active'
  ), '[]'::jsonb) as requirement_constraints,
  coalesce((select jsonb_agg(to_jsonb(f) order by f.analyzer_type, f.title) from active_findings f), '[]'::jsonb) as active_domain_findings,
  (select to_jsonb(f) from finance f) as financial_regression,
  coalesce((select jsonb_agg(to_jsonb(r) order by r.created_at desc) from latest_runs r), '[]'::jsonb) as latest_runs;
