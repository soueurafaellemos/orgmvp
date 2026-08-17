from pathlib import Path


SQL = (Path(__file__).parents[1] / "NAVE_V28_7_2B_CORE_SEMANTIC_DOMAINS.sql").read_text(encoding="utf-8").casefold()


def test_b_sql_creates_core_domains_and_atomic_rpc():
    for name in (
        "project_strategy_elements",
        "project_creative_platforms",
        "project_creative_elements",
        "project_experience_architectures",
        "project_journey_moments",
        "project_core_semantic_truth_status",
        "project_core_semantic_status",
        "apply_project_core_semantics_v2872b",
    ):
        assert name in SQL
    assert "domain_hint" in SQL and "semantic_role" in SQL and "assertion_mode" in SQL
    assert "reconcile_domain_object" in SQL
    assert "legacy_shadow" in SQL


def test_b_sql_does_not_reopen_outcome_truth_gate_or_graph():
    assert "create or replace view public.entity_current_outcomes" not in SQL
    assert "create or replace view public.entity_outcome_truth_status" not in SQL
    assert "cross_source_linker" not in SQL
    assert "canonical_entity_graph" not in SQL
    assert "domain_primary" not in SQL


def test_analyst_inference_is_not_a_core_truth_state():
    # It is allowed as observation vocabulary but must never be a verified domain assertion.
    assert "analyst_inference" in SQL
    truth_segment = SQL.split("create or replace view public.project_core_semantic_truth_status", 1)[1].split("create or replace view public.project_core_semantic_status", 1)[0]
    assert "verified_explicit" in truth_segment
    assert "verified_synthesis" in truth_segment
    assert "human_confirmed" in truth_segment
    assert "analyst_inference" not in truth_segment
