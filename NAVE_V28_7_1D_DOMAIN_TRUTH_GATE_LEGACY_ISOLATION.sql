begin;

-- ============================================================================
-- NAVE by VOE · V28.7.1D — DOMAIN TRUTH GATE & LEGACY ISOLATION
--
-- Additive hardening over V28.7.1B/C. No domain_primary cutover.
--
-- Contracts:
--  1) legacy outcome without auditable provenance cannot be current truth;
--  2) explicit Evidence, evidence-backed Claim or explicit Human Review may
--     qualify an outcome for current-truth resolution;
--  3) confidence / authority never compensate for missing provenance;
--  4) incompatible verified candidates become conflict, never silent winner;
--  5) entity_current_outcomes keeps its V28.7.1B 15-column compatibility;
--  6) V28.6 Graph is frozen by runtime orchestration, not mutated here;
--  7) legacy_shadow remains mandatory.
-- ============================================================================

-- --------------------------------------------------------------------------
-- 0. PREREQUISITES — fail before changing current truth.
-- --------------------------------------------------------------------------
do $$
begin
  if to_regclass('public.entity_outcomes') is null then
    raise exception 'V28.7.1D prerequisite missing: entity_outcomes';
  end if;
  if to_regclass('public.domain_object_evidence') is null then
    raise exception 'V28.7.1D prerequisite missing: domain_object_evidence';
  end if;
  if to_regclass('public.domain_object_governance') is null then
    raise exception 'V28.7.1D prerequisite missing: domain_object_governance';
  end if;
  if to_regclass('public.intelligence_reviews') is null then
    raise exception 'V28.7.1D prerequisite missing: intelligence_reviews / Foundation v1';
  end if;
  if to_regclass('public.knowledge_claims') is null or to_regclass('public.claim_evidence') is null then
    raise exception 'V28.7.1D prerequisite missing: claim provenance / Foundation v1';
  end if;
  if to_regclass('public.intelligence_findings') is null
     or to_regclass('public.finding_evidence') is null
     or to_regclass('public.finding_entities') is null then
    raise exception 'V28.7.1D prerequisite missing: finding infrastructure / Foundation v1';
  end if;
  if to_regprocedure('public.apply_project_domain_normalization_v2871(uuid,uuid,jsonb)') is null then
    raise exception 'V28.7.1D prerequisite missing: apply_project_domain_normalization_v2871';
  end if;
end $$;

-- --------------------------------------------------------------------------
-- 1. OUTCOME TRUTH STATUS
-- Technical state "historical" is used only for non-active/superseded events.
-- Active candidates resolve to verified / inferred / legacy_unverified / conflicted.
-- --------------------------------------------------------------------------
create or replace view public.entity_outcome_truth_status
with (security_invoker = true)
as
with provenance as (
  select
    eo.*,
    coalesce(g.lifecycle_status, 'active') as entity_lifecycle_status,
    lr.decision as latest_review_decision,
    kc.claim_kind as source_claim_kind,
    kc.status as source_claim_status,

    (
      exists (
        select 1
        from public.evidence_units eu
        where eu.id = eo.source_evidence_id
          and eu.is_current = true
      )
      or exists (
        select 1
        from public.domain_object_evidence doe
        join public.evidence_units eu
          on eu.id = doe.evidence_unit_id
         and eu.is_current = true
        where doe.domain_table = 'entity_outcomes'
          and doe.domain_id = eo.id
          and doe.link_role in ('outcome_support','supports','source')
      )
    ) as has_direct_evidence,

    (
      eo.source_claim_id is not null
      and kc.status = 'active'
      and exists (
        select 1
        from public.claim_evidence ce
        join public.evidence_units eu
          on eu.id = ce.evidence_unit_id
         and eu.is_current = true
        where ce.claim_id = eo.source_claim_id
          and ce.support_type = 'supports'
      )
    ) as has_claim_evidence,

    coalesce(lr.decision = 'confirm', false) as has_human_review,

    (
      exists (
        select 1
        from public.domain_object_evidence doe
        join public.evidence_units eu
          on eu.id = doe.evidence_unit_id
         and eu.is_current = true
        where doe.domain_table = 'entity_outcomes'
          and doe.domain_id = eo.id
          and doe.link_role = 'contradicts'
      )
      or (
        eo.source_claim_id is not null
        and exists (
          select 1
          from public.claim_evidence ce
          join public.evidence_units eu
            on eu.id = ce.evidence_unit_id
           and eu.is_current = true
          where ce.claim_id = eo.source_claim_id
            and ce.support_type = 'contradicts'
        )
      )
    ) as has_contradicting_evidence
  from public.entity_outcomes eo
  left join public.domain_object_governance g
    on g.entity_id = eo.entity_id
  left join public.knowledge_claims kc
    on kc.id = eo.source_claim_id
  left join lateral (
    select ir.decision
    from public.intelligence_reviews ir
    where ir.object_type = 'outcome'
      and ir.object_id = eo.id
    order by ir.created_at desc, ir.id desc
    limit 1
  ) lr on true
),
eligibility as (
  select
    p.*,
    (
      p.event_status = 'active'
      and p.entity_lifecycle_status = 'active'
      and coalesce(p.latest_review_decision, '') not in ('reject','correct','merge','split','needs_evidence')
      and not p.has_contradicting_evidence
      and (
        p.has_human_review
        or p.has_direct_evidence
        or (p.has_claim_evidence and coalesce(p.source_claim_kind, 'fact') <> 'inference')
      )
    ) as verified_candidate,
    (
      p.event_status = 'active'
      and p.entity_lifecycle_status = 'active'
      and not p.has_direct_evidence
      and not p.has_human_review
      and p.has_claim_evidence
      and p.source_claim_kind = 'inference'
      and coalesce(p.latest_review_decision, '') not in ('reject','correct','merge','split','needs_evidence')
      and not p.has_contradicting_evidence
    ) as inferred_candidate
  from provenance p
),
conflict_groups as (
  select
    entity_id,
    outcome_type,
    count(distinct outcome_status)::integer as verified_status_count
  from eligibility
  where verified_candidate = true
  group by entity_id, outcome_type
),
classified as (
  select
    e.*,
    coalesce(cg.verified_status_count, 0) as verified_status_count,
    case
      when e.event_status <> 'active' or e.entity_lifecycle_status <> 'active' then 'historical'
      when coalesce(e.latest_review_decision, '') in ('reject','correct','merge','split','needs_evidence') then 'conflicted'
      when e.has_contradicting_evidence then 'conflicted'
      when e.verified_candidate and coalesce(cg.verified_status_count, 0) > 1 then 'conflicted'
      when e.verified_candidate then 'verified'
      when e.inferred_candidate then 'inferred'
      else 'legacy_unverified'
    end as truth_state,
    case
      when e.has_human_review then 'human_review'
      when e.has_direct_evidence then 'direct_evidence'
      when e.has_claim_evidence then 'claim_evidence'
      else 'legacy_only'
    end as provenance_method
  from eligibility e
  left join conflict_groups cg
    on cg.entity_id = e.entity_id
   and cg.outcome_type = e.outcome_type
)
select
  c.*,
  case when c.truth_state = 'verified' then coalesce(c.authority_score, 0) else 0::numeric end as effective_authority_score
from classified c;

comment on view public.entity_outcome_truth_status is
  'V28.7.1D — auditoria de truth/provenance de cada outcome. Legacy sem Evidence/Claim-evidence/Review continua preservado, mas não decide current truth.';

-- --------------------------------------------------------------------------
-- 2. CURRENT TRUTH RESOLVER
-- IMPORTANT: preserve all 15 existing columns and their order from V28.7.1B.
-- --------------------------------------------------------------------------
create or replace view public.entity_current_outcomes
with (security_invoker = true)
as
select distinct on (entity_id, outcome_type)
  id,
  entity_id,
  project_id,
  outcome_type,
  outcome_status,
  outcome_at,
  reason,
  source_claim_id,
  source_evidence_id,
  confidence,
  authority_score,
  is_human_confirmed,
  attributes,
  created_at,
  event_status
from public.entity_outcome_truth_status ots
where ots.event_status = 'active'
  and ots.truth_state = 'verified'
order by
  entity_id,
  outcome_type,
  effective_authority_score desc nulls last,
  outcome_at desc nulls last,
  created_at desc;

comment on view public.entity_current_outcomes is
  'V28.7.1D — current truth contém somente outcomes verified. Authority desempata candidatos elegíveis; nunca substitui provenance.';

-- --------------------------------------------------------------------------
-- 3. ADDITIVE APPLY WRAPPER
-- Reuses the already-proven V28.7.1 transactional writer. The new resolver is
-- active before the inner RPC projects proposal/execution status, so caches are
-- derived from verified truth. Wrapper stamps the new schema version atomically.
-- --------------------------------------------------------------------------
create or replace function public.apply_project_domain_normalization_v2871d(
  p_project_id uuid,
  p_run_id uuid,
  p_bundle jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_result jsonb;
begin
  v_result := public.apply_project_domain_normalization_v2871(
    p_project_id,
    p_run_id,
    p_bundle
  );

  update public.project_domain_migration_state
  set migration_mode = 'legacy_shadow',
      domain_schema_version = '28.7.1d',
      last_completed_run_id = p_run_id,
      updated_at = now()
  where project_id = p_project_id;

  update public.intelligence_runs
  set metadata = coalesce(metadata, '{}'::jsonb) || jsonb_build_object(
        'domain_schema_version', '28.7.1d',
        'truth_gate', true,
        'legacy_isolation', true,
        'graph_v286', 'frozen'
      )
  where id = p_run_id;

  return coalesce(v_result, '{}'::jsonb) || jsonb_build_object(
    'status', 'completed',
    'domain_schema_version', '28.7.1d',
    'migration_mode', 'legacy_shadow',
    'truth_gate', true
  );
end;
$$;

revoke all on function public.apply_project_domain_normalization_v2871d(uuid,uuid,jsonb) from public, anon, authenticated;
grant execute on function public.apply_project_domain_normalization_v2871d(uuid,uuid,jsonb) to service_role, postgres;

-- --------------------------------------------------------------------------
-- 4. INTEGRITY STATUS — preserve V28.7.1B prefix, append Truth/Audit columns.
-- --------------------------------------------------------------------------
create or replace view public.project_domain_integrity_status
with (security_invoker = true)
as
select
  p.id as project_id,
  (select count(*)::integer
     from public.project_solution_instances psi
     left join public.domain_object_governance g on g.entity_id = psi.entity_id
    where psi.project_id = p.id and coalesce(g.lifecycle_status,'active') = 'active') as solution_instances,
  (select count(*)::integer
     from public.project_solution_occurrences pso
     join public.project_solution_instances psi on psi.id = pso.solution_instance_id
     left join public.domain_object_governance g on g.entity_id = psi.entity_id
    where pso.project_id = p.id
      and pso.lifecycle_status = 'active'
      and coalesce(g.lifecycle_status,'active') = 'active') as solution_occurrences,
  (select count(*)::integer
     from public.project_solution_occurrences pso
     join public.project_solution_instances psi on psi.id = pso.solution_instance_id
     left join public.domain_object_governance g on g.entity_id = psi.entity_id
    where pso.project_id = p.id
      and pso.lifecycle_status = 'active'
      and pso.evidence_unit_id is not null
      and coalesce(g.lifecycle_status,'active') = 'active') as occurrences_with_evidence,
  (select count(*)::integer
     from public.project_requirements pr
     left join public.domain_object_governance g on g.entity_id = pr.entity_id
    where pr.project_id = p.id and coalesce(g.lifecycle_status,'active') = 'active') as requirements,
  (select count(distinct doe.domain_id)::integer
     from public.domain_object_evidence doe
     join public.evidence_units eu on eu.id = doe.evidence_unit_id and eu.is_current = true
     left join public.domain_object_governance g on g.entity_id = doe.object_entity_id
    where doe.project_id = p.id
      and doe.domain_table = 'project_requirements'
      and coalesce(g.lifecycle_status,'active') = 'active') as requirements_with_evidence,
  (select count(*)::integer from public.financial_documents fd where fd.project_id = p.id) as financial_documents,
  (select count(*)::integer
     from public.financial_line_items fli
     left join public.domain_object_governance g on g.entity_id = fli.entity_id
    where fli.project_id = p.id and coalesce(g.lifecycle_status,'active') = 'active') as financial_line_items,
  (select count(distinct doe.domain_id)::integer
     from public.domain_object_evidence doe
     join public.evidence_units eu on eu.id = doe.evidence_unit_id and eu.is_current = true
     left join public.domain_object_governance g on g.entity_id = doe.object_entity_id
    where doe.project_id = p.id
      and doe.domain_table = 'financial_line_items'
      and coalesce(g.lifecycle_status,'active') = 'active') as financial_lines_with_evidence,
  (select count(*)::integer from public.entity_current_outcomes eco where eco.project_id = p.id) as current_outcomes,
  (select count(*)::integer
     from public.domain_object_evidence doe
     join public.evidence_units eu on eu.id = doe.evidence_unit_id and eu.is_current = true
     left join public.domain_object_governance g on g.entity_id = doe.object_entity_id
    where doe.project_id = p.id and coalesce(g.lifecycle_status,'active') = 'active') as evidence_links,
  (select migration_mode from public.project_domain_migration_state pdms where pdms.project_id = p.id) as migration_mode,
  (select domain_schema_version from public.project_domain_migration_state pdms where pdms.project_id = p.id) as domain_schema_version,
  (select last_completed_run_id from public.project_domain_migration_state pdms where pdms.project_id = p.id) as last_completed_run_id,
  (select count(*)::integer from public.memory_items mi where mi.project_id = p.id) as legacy_memory_items,
  (select count(*)::integer from public.memory_briefing_requirements mbr where mbr.project_id = p.id) as legacy_requirements,
  (select count(*)::integer from public.memory_cost_documents mcd where mcd.project_id = p.id) as legacy_cost_documents,
  (select count(*)::integer from public.memory_cost_items mci where mci.project_id = p.id) as legacy_cost_items,

  -- V28.7.1D appended columns start here.
  (select count(*)::integer from public.entity_outcome_truth_status ots where ots.project_id = p.id and ots.event_status = 'active') as outcomes_total,
  (select count(*)::integer from public.entity_outcome_truth_status ots where ots.project_id = p.id and ots.event_status = 'active' and ots.truth_state = 'verified') as outcomes_verified,
  (select count(*)::integer from public.entity_outcome_truth_status ots where ots.project_id = p.id and ots.event_status = 'active' and ots.truth_state = 'inferred') as outcomes_inferred,
  (select count(*)::integer from public.entity_outcome_truth_status ots where ots.project_id = p.id and ots.event_status = 'active' and ots.truth_state = 'legacy_unverified') as outcomes_legacy_unverified,
  (select count(*)::integer from public.entity_outcome_truth_status ots where ots.project_id = p.id and ots.event_status = 'active' and ots.truth_state = 'conflicted') as outcomes_conflicted,

  (select count(*)::integer from public.entity_outcome_truth_status ots where ots.project_id = p.id and ots.event_status = 'active' and ots.outcome_type = 'proposal_status') as proposal_outcomes_total,
  (select count(*)::integer from public.entity_outcome_truth_status ots where ots.project_id = p.id and ots.event_status = 'active' and ots.outcome_type = 'proposal_status' and ots.truth_state = 'verified') as proposal_outcomes_verified,
  (select count(*)::integer from public.entity_outcome_truth_status ots where ots.project_id = p.id and ots.event_status = 'active' and ots.outcome_type = 'execution_status') as execution_outcomes_total,
  (select count(*)::integer from public.entity_outcome_truth_status ots where ots.project_id = p.id and ots.event_status = 'active' and ots.outcome_type = 'execution_status' and ots.truth_state = 'verified') as execution_outcomes_verified,
  (select count(*)::integer from public.entity_outcome_truth_status ots where ots.project_id = p.id and ots.event_status = 'active' and ots.outcome_type = 'commercial_result') as commercial_outcomes_total,
  (select count(*)::integer from public.entity_outcome_truth_status ots where ots.project_id = p.id and ots.event_status = 'active' and ots.outcome_type = 'commercial_result' and ots.truth_state = 'verified') as commercial_outcomes_verified,

  (select count(*)::integer
     from public.intelligence_findings f
     join public.knowledge_entities ke on ke.id = f.scope_entity_id
    where ke.domain_table = 'projects'
      and ke.domain_id = p.id
      and f.analyzer_type = 'domain_coverage_audit'
      and f.status = 'active') as coverage_findings_open,
  (select count(*)::integer
     from public.intelligence_findings f
     join public.knowledge_entities ke on ke.id = f.scope_entity_id
    where ke.domain_table = 'projects'
      and ke.domain_id = p.id
      and f.analyzer_type = 'domain_identity_audit'
      and f.status = 'active') as identity_conflicts_open,

  not exists (
    select 1
    from public.entity_outcome_truth_status ots
    where ots.project_id = p.id
      and ots.event_status = 'active'
      and ots.truth_state = 'conflicted'
  ) as truth_gate_passed
from public.projects p;

comment on view public.project_domain_integrity_status is
  'V28.7.1D — integridade do domínio com Truth Gate, isolation de legacy outcome e contagem dos audits de coverage/identity.';

-- project_domain_normalization_status remains compatible because the original
-- project_domain_integrity_status column prefix and names were preserved.

-- --------------------------------------------------------------------------
-- 5. PERMISSIONS
-- --------------------------------------------------------------------------
revoke all on public.entity_outcome_truth_status from anon, authenticated;
revoke all on public.entity_current_outcomes from anon, authenticated;
revoke all on public.project_domain_integrity_status from anon, authenticated;
grant select on public.entity_outcome_truth_status to service_role, postgres;
grant select on public.entity_current_outcomes to service_role, postgres;
grant select on public.project_domain_integrity_status to service_role, postgres;

-- --------------------------------------------------------------------------
-- 6. INSTALL SELF-CHECK
-- --------------------------------------------------------------------------
do $$
begin
  if to_regclass('public.entity_outcome_truth_status') is null then
    raise exception 'V28.7.1D install check failed: entity_outcome_truth_status missing';
  end if;
  if to_regprocedure('public.apply_project_domain_normalization_v2871d(uuid,uuid,jsonb)') is null then
    raise exception 'V28.7.1D install check failed: normalization wrapper missing';
  end if;
  if not exists (
    select 1 from information_schema.columns
    where table_schema = 'public'
      and table_name = 'entity_current_outcomes'
      and column_name = 'created_at'
      and ordinal_position = 14
  ) then
    raise exception 'V28.7.1D install check failed: entity_current_outcomes.created_at must remain column 14';
  end if;
  if not exists (
    select 1 from information_schema.columns
    where table_schema = 'public'
      and table_name = 'entity_current_outcomes'
      and column_name = 'event_status'
      and ordinal_position = 15
  ) then
    raise exception 'V28.7.1D install check failed: entity_current_outcomes.event_status must remain column 15';
  end if;
  if not exists (
    select 1 from information_schema.columns
    where table_schema = 'public'
      and table_name = 'project_domain_integrity_status'
      and column_name = 'truth_gate_passed'
  ) then
    raise exception 'V28.7.1D install check failed: truth_gate_passed missing';
  end if;
end $$;

notify pgrst, 'reload schema';

commit;
