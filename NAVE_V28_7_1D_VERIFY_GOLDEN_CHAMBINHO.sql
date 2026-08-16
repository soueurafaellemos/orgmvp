-- NAVE by VOE · V28.7.1D — Golden Chambinho Verification
-- READ ONLY. Não altera dados.
-- Execute somente DEPOIS do SQL V28.7.1D, do deploy GitHub e de
-- "Atualizar domínio e auditar verdade" no Festivalzinho Chambinho.
--
-- O alvo é o projeto mais recente cujo nome/evento/marca contém "chambinho".
-- A primeira consulta mostra explicitamente qual projeto foi selecionado.

-- ---------------------------------------------------------------------------
-- 0. TARGET PROJECT
-- ---------------------------------------------------------------------------
with target_project as (
  select p.*
  from public.projects p
  where concat_ws(' ', p.project_name, p.event_name, p.client_brand) ilike '%chambinho%'
  order by p.updated_at desc nulls last, p.created_at desc
  limit 1
)
select
  id as project_id,
  project_name,
  event_name,
  client_brand,
  status as projects_status_cache,
  updated_at
from target_project;

-- ---------------------------------------------------------------------------
-- 1. DOMAIN INTEGRITY / TRUTH GATE
-- ---------------------------------------------------------------------------
with target_project as (
  select p.id
  from public.projects p
  where concat_ws(' ', p.project_name, p.event_name, p.client_brand) ilike '%chambinho%'
  order by p.updated_at desc nulls last, p.created_at desc
  limit 1
)
select
  s.project_id,
  s.solution_instances,
  s.solution_occurrences,
  s.occurrences_with_evidence,
  s.requirements,
  s.requirements_with_evidence,
  s.financial_line_items,
  s.financial_lines_with_evidence,
  s.current_outcomes,
  s.outcomes_total,
  s.outcomes_verified,
  s.outcomes_inferred,
  s.outcomes_legacy_unverified,
  s.outcomes_conflicted,
  s.proposal_outcomes_verified,
  s.proposal_outcomes_total,
  s.execution_outcomes_verified,
  s.execution_outcomes_total,
  s.commercial_outcomes_verified,
  s.commercial_outcomes_total,
  s.coverage_findings_open,
  s.identity_conflicts_open,
  s.truth_gate_passed,
  s.migration_mode,
  s.domain_schema_version,
  s.last_completed_run_id
from public.project_domain_integrity_status s
join target_project tp on tp.id = s.project_id;

-- ---------------------------------------------------------------------------
-- 2. ALL ACTIVE OUTCOME CANDIDATES — verified x legacy x conflict
-- ---------------------------------------------------------------------------
with target_project as (
  select p.id
  from public.projects p
  where concat_ws(' ', p.project_name, p.event_name, p.client_brand) ilike '%chambinho%'
  order by p.updated_at desc nulls last, p.created_at desc
  limit 1
)
select
  ots.id as outcome_id,
  ke.canonical_name as subject,
  ots.outcome_type,
  ots.outcome_status,
  ots.truth_state,
  ots.provenance_method,
  ots.has_direct_evidence,
  ots.has_claim_evidence,
  ots.has_human_review,
  ots.confidence,
  ots.authority_score,
  ots.effective_authority_score,
  ots.legacy_source_table,
  ots.legacy_source_id,
  ots.source_evidence_id,
  sa.canonical_file_name as direct_evidence_file,
  eu.unit_type as direct_evidence_unit_type,
  eu.locator as direct_evidence_locator,
  left(coalesce(eu.content_text, ''), 500) as direct_evidence_excerpt
from public.entity_outcome_truth_status ots
join target_project tp on tp.id = ots.project_id
join public.knowledge_entities ke on ke.id = ots.entity_id
left join public.evidence_units eu on eu.id = ots.source_evidence_id and eu.is_current = true
left join public.source_assets sa on sa.id = eu.source_asset_id
where ots.event_status = 'active'
order by ots.outcome_type, ots.truth_state, subject, ots.outcome_status;

-- ---------------------------------------------------------------------------
-- 3. CURRENT TRUTH ONLY
-- Expected semantic check for Golden: process_type=direct and
-- commercial_result=not_applicable; unverified won/approved cannot appear here.
-- ---------------------------------------------------------------------------
with target_project as (
  select p.id
  from public.projects p
  where concat_ws(' ', p.project_name, p.event_name, p.client_brand) ilike '%chambinho%'
  order by p.updated_at desc nulls last, p.created_at desc
  limit 1
)
select
  eco.id as outcome_id,
  ke.canonical_name as subject,
  eco.outcome_type,
  eco.outcome_status,
  eco.authority_score,
  eco.source_evidence_id,
  sa.canonical_file_name as evidence_file,
  eu.locator as evidence_locator,
  left(coalesce(eu.content_text, ''), 500) as evidence_excerpt
from public.entity_current_outcomes eco
join target_project tp on tp.id = eco.project_id
join public.knowledge_entities ke on ke.id = eco.entity_id
left join public.evidence_units eu on eu.id = eco.source_evidence_id and eu.is_current = true
left join public.source_assets sa on sa.id = eu.source_asset_id
order by eco.outcome_type, subject;

-- ---------------------------------------------------------------------------
-- 4. REQUIREMENT PROVENANCE
-- Golden gate: 14/14 evidence-backed. Público-alvo, Objetivo principal e Budget
-- must no longer be false negatives. This does NOT validate budget operator/value.
-- ---------------------------------------------------------------------------
with target_project as (
  select p.id
  from public.projects p
  where concat_ws(' ', p.project_name, p.event_name, p.client_brand) ilike '%chambinho%'
  order by p.updated_at desc nulls last, p.created_at desc
  limit 1
), requirement_support as (
  select
    pr.id,
    count(distinct doe.evidence_unit_id) filter (where eu.is_current = true)::integer as evidence_units,
    string_agg(distinct sa.canonical_file_name, ' | ') filter (where eu.is_current = true) as evidence_files
  from public.project_requirements pr
  join target_project tp on tp.id = pr.project_id
  left join public.domain_object_evidence doe
    on doe.domain_table = 'project_requirements'
   and doe.domain_id = pr.id
   and doe.link_role in ('source','supports','partially_supports')
  left join public.evidence_units eu on eu.id = doe.evidence_unit_id
  left join public.source_assets sa on sa.id = eu.source_asset_id
  group by pr.id
)
select
  pr.requirement_type,
  pr.title,
  pr.description,
  coalesce(rs.evidence_units, 0) as evidence_units,
  rs.evidence_files,
  pr.constraint_operator,
  pr.constraint_value,
  pr.unit,
  case when coalesce(rs.evidence_units, 0) > 0 then 'VERIFIED_PROVENANCE' else 'MISSING_PROVENANCE' end as provenance_gate
from public.project_requirements pr
join target_project tp on tp.id = pr.project_id
left join requirement_support rs on rs.id = pr.id
order by pr.requirement_type, pr.title;

-- ---------------------------------------------------------------------------
-- 5. COVERAGE + IDENTITY FINDINGS
-- Golden expected minimum: Amarelinha/Pescaria as coverage gaps and
-- Chaveiro ↔ Pelúcia as identity review, if the stored evidence matches the audit.
-- ---------------------------------------------------------------------------
with target_project as (
  select p.id
  from public.projects p
  where concat_ws(' ', p.project_name, p.event_name, p.client_brand) ilike '%chambinho%'
  order by p.updated_at desc nulls last, p.created_at desc
  limit 1
), project_entity as (
  select ke.id
  from public.knowledge_entities ke
  join target_project tp on ke.domain_table = 'projects' and ke.domain_id = tp.id
  limit 1
)
select
  f.analyzer_type,
  f.finding_type,
  f.title,
  f.finding_kind,
  f.importance,
  f.confidence,
  f.statement,
  f.recommended_action,
  f.status,
  (
    select string_agg(distinct ke2.canonical_name || ' [' || fe.role || ']', ' | ')
    from public.finding_entities fe
    join public.knowledge_entities ke2 on ke2.id = fe.entity_id
    where fe.finding_id = f.id
  ) as related_entities,
  (
    select count(*)::integer
    from public.finding_evidence f_ev
    join public.evidence_units eu on eu.id = f_ev.evidence_unit_id and eu.is_current = true
    where f_ev.finding_id = f.id
  ) as current_evidence_units
from public.intelligence_findings f
join project_entity pe on pe.id = f.scope_entity_id
where f.analyzer_type in ('domain_coverage_audit','domain_identity_audit')
  and f.status = 'active'
order by f.analyzer_type, f.importance desc, f.title;

-- ---------------------------------------------------------------------------
-- 6. FINANCIAL REGRESSION GATE
-- Golden expected: 54 lines / 54 Evidence Units / 54 sheet+row locators /
-- R$ 554.310,85. This is a regression gate, not a recalculation of source truth.
-- ---------------------------------------------------------------------------
with target_project as (
  select p.id
  from public.projects p
  where concat_ws(' ', p.project_name, p.event_name, p.client_brand) ilike '%chambinho%'
  order by p.updated_at desc nulls last, p.created_at desc
  limit 1
), financial as (
  select
    fli.id,
    fli.total_value,
    fli.source_evidence_id,
    eu.locator,
    concat_ws('::', coalesce(eu.locator->>'sheet',''), coalesce(eu.locator->>'row','')) as sheet_row
  from public.financial_line_items fli
  join target_project tp on tp.id = fli.project_id
  left join public.evidence_units eu on eu.id = fli.source_evidence_id and eu.is_current = true
)
select
  count(*)::integer as financial_lines,
  count(distinct source_evidence_id)::integer as distinct_evidence_units,
  count(distinct nullif(sheet_row, '::'))::integer as distinct_sheet_row_locators,
  round(coalesce(sum(total_value), 0)::numeric, 2) as total_brl,
  count(*) filter (where source_evidence_id is null)::integer as lines_without_direct_evidence
from financial;

-- ---------------------------------------------------------------------------
-- 7. GRAPH FREEZE PROXY
-- The V28.7.1D runtime contains no V28.6 Graph/Cross-Source rebuild call.
-- This query verifies that the latest domain-normalization run is newer than the
-- latest cross_source_linker run for this project (or no cross-source run exists).
-- ---------------------------------------------------------------------------
with target_project as (
  select p.id
  from public.projects p
  where concat_ws(' ', p.project_name, p.event_name, p.client_brand) ilike '%chambinho%'
  order by p.updated_at desc nulls last, p.created_at desc
  limit 1
), project_entity as (
  select ke.id
  from public.knowledge_entities ke
  join target_project tp on ke.domain_table = 'projects' and ke.domain_id = tp.id
  limit 1
), runs as (
  select
    max(ir.created_at) filter (where ir.analyzer_type = 'domain_normalization') as last_domain_run,
    max(ir.created_at) filter (where ir.analyzer_type = 'domain_coverage_audit') as last_coverage_audit,
    max(ir.created_at) filter (where ir.analyzer_type = 'domain_identity_audit') as last_identity_audit,
    max(ir.created_at) filter (where ir.analyzer_type = 'cross_source_linker') as last_cross_source_run
  from public.intelligence_runs ir
  join project_entity pe on pe.id = ir.scope_entity_id
)
select
  last_domain_run,
  last_coverage_audit,
  last_identity_audit,
  last_cross_source_run,
  case
    when last_domain_run is null then false
    when last_cross_source_run is null then true
    else last_cross_source_run < last_domain_run
  end as cross_source_not_rebuilt_in_latest_domain_round
from runs;

-- ---------------------------------------------------------------------------
-- 8. SOLUTION STATUS PROJECTIONS
-- Execution legacy without provenance should fall back to not_confirmed.
-- ---------------------------------------------------------------------------
with target_project as (
  select p.id
  from public.projects p
  where concat_ws(' ', p.project_name, p.event_name, p.client_brand) ilike '%chambinho%'
  order by p.updated_at desc nulls last, p.created_at desc
  limit 1
)
select
  psi.name,
  psi.solution_kind,
  psi.proposal_status,
  psi.execution_status,
  psi.identity_key
from public.project_solution_instances psi
join target_project tp on tp.id = psi.project_id
order by psi.name;
