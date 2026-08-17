from pathlib import Path


SQL = (Path(__file__).parents[1] / "NAVE_V28_7_2C0_REQUIREMENT_SEMANTIC_RECONCILIATION.sql").read_text(encoding="utf-8").casefold()


def test_c0_sql_adds_requirement_occurrence_truth_status_and_atomic_rpc():
    for name in (
        "project_requirement_occurrences",
        "project_requirement_truth_status",
        "project_requirement_reconciliation_status",
        "apply_project_requirement_reconciliation_v2872c0",
    ):
        assert name in SQL
    assert "requirement identity != requirement occurrence != constraint" in SQL
    assert "attach_requirement_occurrence" in SQL
    assert "attach_scope" in SQL
    assert "attach_attribute" in SQL
    assert "attach_constraint" in SQL


def test_c0_truth_gate_does_not_treat_legacy_presence_as_provenance():
    truth = SQL.split("create or replace view public.project_requirement_truth_status", 1)[1].split("create or replace view public.project_requirement_reconciliation_status", 1)[0]
    assert "has_direct_domain_evidence" in truth
    assert "has_current_occurrence" in truth
    assert "legacy_unverified" in truth
    assert "human_confirmed" in truth


def test_c0_has_no_cutover_graph_or_destructive_requirement_delete():
    assert "domain_primary" not in SQL
    assert "canonical_entity_graph" not in SQL
    assert "cross_source_linker" not in SQL
    assert "delete from public.project_requirements" not in SQL
    assert "never auto-merges two existing" in SQL


def test_c0_keeps_solution_debugger_scoped_away_from_requirement_observations():
    status_view = SQL.split("create or replace view public.project_semantic_observation_status", 1)[1].split("create or replace view public.project_requirement_truth_status", 1)[0]
    assert "'requirement'" in status_view
    assert "domain_hint" in status_view
