from pathlib import Path


ROOT = Path(__file__).parents[1]
SQL = (ROOT / "NAVE_V28_7_2A_RECONCILIATION_KERNEL.sql").read_text(encoding="utf-8")


def test_sql_creates_pre_domain_observation_context_and_constraints():
    assert "create table if not exists public.semantic_observations" in SQL
    assert "create table if not exists public.project_context_elements" in SQL
    assert "create table if not exists public.project_requirement_constraints" in SQL
    assert "'semantic_observation'" in SQL
    assert "source_observation_id" in SQL
    assert "observed_status text" in SQL
    assert "'unspecified'" in SQL


def test_sql_expands_occurrence_lifecycle_without_replacing_occurrence_table():
    assert "'post_event'" in SQL
    assert "'budget_reference'" in SQL
    assert "'feedback_context'" in SQL
    assert "create table if not exists public.project_solution_occurrences" not in SQL


def test_sql_keeps_truth_gate_and_shadow_cutover_contract():
    assert "apply_project_domain_reconciliation_v2872a" in SQL
    assert "migration_mode = 'legacy_shadow'" in SQL
    assert "'28.7.2a'" in SQL and "domain_schema_version" in SQL
    assert "create or replace view public.entity_current_outcomes" not in SQL
    assert "drop table" not in SQL.lower()


def test_execution_outcome_is_evidence_backed_and_projection_uses_current_truth():
    assert "source_evidence_id, source_observation_id" in SQL
    assert "from public.entity_current_outcomes eco" in SQL
    assert "eco.outcome_type = 'execution_status'" in SQL


def test_sql_preserves_monotonic_private_writer_permissions():
    assert "revoke all on function public.apply_project_domain_reconciliation_v2872a" in SQL
    assert "grant select, insert, update on public.%I to service_role" in SQL
    assert "grant select, insert, update, delete on public.%I to service_role" not in SQL


def test_rpc_is_definer_because_outcomes_are_append_only_for_service_role():
    assert "security definer" in SQL.lower()
    assert "security invoker\nset search_path = public, extensions" not in SQL.lower()

def test_requirement_constraint_uses_direct_evidence_not_false_child_mirror():
    assert "project_requirement_constraints.source_evidence_id" in SQL or "source_evidence_id uuid not null" in SQL
    assert "'project_requirement_constraints',\n      (v_item->>'id')::uuid" not in SQL


def test_reconciliation_status_exposes_open_observations_without_calling_them_resolved():
    assert "as observations_open" in SQL
    assert "as evidence_reconciliation_coverage_pct" in SQL
    assert "legacy_independence_ratio_pct" not in SQL


def test_status_metrics_use_current_evidence_and_current_truth():
    assert "eu.is_current = true" in SQL
    assert "from public.entity_current_outcomes eco" in SQL
    assert "as verified_execution_outcomes" in SQL

VERIFY = (ROOT / "NAVE_V28_7_2A_VERIFY_GOLDEN_CHAMBINHO.sql").read_text(encoding="utf-8")


def test_golden_verify_checks_semantics_not_only_counts():
    assert "all_expected_executions_current" in VERIFY
    assert "execution_truth_is_exactly_expected_set" in VERIFY
    assert "no_logistics_promoted_to_solution" in VERIFY
    assert "pelucia_chaveiro_remain_distinct" in VERIFY
    assert "pelucia_chaveiro_review_signal_present" in VERIFY
    assert "coverage_gaps_reconciled" in VERIFY
    assert "commercial_process_direct_current" in VERIFY
    assert "commercial_not_applicable_current" in VERIFY
    assert "legacy_unverified_never_current" in VERIFY


def test_golden_verify_keeps_budget_operator_fail_closed():
    assert "budget_constraint_400k_scoped" in VERIFY
    assert "prc.operator='envelope'" not in VERIFY
    assert "prc.operator in ('unspecified','=','<=','>=','envelope','other')" in VERIFY
