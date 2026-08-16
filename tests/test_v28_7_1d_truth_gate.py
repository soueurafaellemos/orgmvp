from pathlib import Path
import re


def _current_outcome_columns(sql: str) -> list[str]:
    pattern = r"create or replace view public\.entity_current_outcomes.*?select distinct on \(entity_id, outcome_type\)(.*?)from public\.entity_outcome_truth_status"
    match = re.search(pattern, sql, flags=re.I | re.S)
    assert match, "entity_current_outcomes V28.7.1D not found"
    return [
        line.strip().strip(",")
        for line in match.group(1).splitlines()
        if line.strip() and not line.strip().startswith("--")
    ]


def test_truth_gate_requires_auditable_provenance_and_isolates_legacy():
    root = Path(__file__).parents[1]
    sql = (root / "NAVE_V28_7_1D_DOMAIN_TRUTH_GATE_LEGACY_ISOLATION.sql").read_text(encoding="utf-8").casefold()
    assert "create or replace view public.entity_outcome_truth_status" in sql
    assert "has_direct_evidence" in sql
    assert "has_claim_evidence" in sql
    assert "has_human_review" in sql
    assert "legacy_unverified" in sql
    assert "truth_state = 'verified'" in sql
    assert "effective_authority_score" in sql
    assert "latest_review_decision" in sql
    assert "ce.support_type = 'supports'" in sql
    assert "eu.is_current = true" in sql


def test_current_outcome_view_preserves_15_column_compatibility():
    root = Path(__file__).parents[1]
    sql = (root / "NAVE_V28_7_1D_DOMAIN_TRUTH_GATE_LEGACY_ISOLATION.sql").read_text(encoding="utf-8")
    assert _current_outcome_columns(sql) == [
        "id", "entity_id", "project_id", "outcome_type", "outcome_status",
        "outcome_at", "reason", "source_claim_id", "source_evidence_id",
        "confidence", "authority_score", "is_human_confirmed", "attributes",
        "created_at", "event_status",
    ]
    folded = sql.casefold()
    assert "ordinal_position = 14" in folded
    assert "ordinal_position = 15" in folded


def test_conflicting_verified_outcomes_do_not_silently_win():
    sql = (Path(__file__).parents[1] / "NAVE_V28_7_1D_DOMAIN_TRUTH_GATE_LEGACY_ISOLATION.sql").read_text(encoding="utf-8").casefold()
    assert "count(distinct outcome_status)" in sql
    assert "verified_status_count" in sql
    assert "then 'conflicted'" in sql
    # Current resolver contains only verified candidates, so conflicted rows disappear.
    assert "and ots.truth_state = 'verified'" in sql


def test_wrapper_keeps_legacy_shadow_and_reuses_transactional_writer():
    sql = (Path(__file__).parents[1] / "NAVE_V28_7_1D_DOMAIN_TRUTH_GATE_LEGACY_ISOLATION.sql").read_text(encoding="utf-8").casefold()
    assert "apply_project_domain_normalization_v2871d" in sql
    assert "v_result := public.apply_project_domain_normalization_v2871" in sql
    assert "migration_mode = 'legacy_shadow'" in sql
    assert "domain_schema_version = '28.7.1d'" in sql
    assert "domain_primary" not in sql.split("create or replace function public.apply_project_domain_normalization_v2871d", 1)[1].split("end;", 1)[0]
