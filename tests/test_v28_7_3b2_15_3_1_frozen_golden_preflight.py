from pathlib import Path
import json
from project_requirement_response_truth_transaction import (
    JOVI, CHAMBINHO, _load_locked_projection,
    build_transaction_preflight_from_projection,
)


def test_frozen_baseline_hashes_and_versions():
    for pid in (JOVI, CHAMBINHO):
        projection, spec = _load_locked_projection(pid)
        assert projection["version"] == "V28.7.3B2.15.2.1"
        assert projection["all_checks_pass"] is True
        assert spec["actual_sha256"] == spec["sha256"]


def test_jovi_frozen_projection_is_no_transaction():
    projection, _ = _load_locked_projection(JOVI)
    result = build_transaction_preflight_from_projection(
        project_id=JOVI,
        projection=projection,
    )
    assert result["status"] == "NO_TRANSACTION_REQUIRED"
    assert result["projected_event_count"] == 0
    assert result["ready_for_probe"] is False
    assert result["ready_for_real_write"] is False


def test_chambinho_frozen_projection_is_probe_only():
    projection, _ = _load_locked_projection(CHAMBINHO)
    result = build_transaction_preflight_from_projection(
        project_id=CHAMBINHO,
        projection=projection,
    )
    assert result["status"] == "READY_FOR_ROLLBACK_ONLY_PROBE"
    assert result["projected_event_count"] == 3
    assert result["projected_evidence_link_count"] == 3
    assert result["ready_for_real_write"] is False


def test_heavy_projection_chain_removed():
    root = Path(__file__).resolve().parents[1]
    source = (root / "project_requirement_response_truth_transaction.py").read_text()
    assert "run_contract_verified_response_truth_projection_shadow" not in source
    assert "project_requirement_auto_adjudication_completeness" not in source
    assert "project_requirement_response_truth_eligibility_shadow" not in source
