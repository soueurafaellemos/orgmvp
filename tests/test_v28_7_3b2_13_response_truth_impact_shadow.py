from pathlib import Path

from project_requirement_response_truth_impact_shadow import (
    compare_response_projection_integrity,
)


def _projection(rid: str, title: str = "A", status: str = "response_review_partial"):
    return {
        "requirement_id": rid,
        "title": title,
        "canonical_obligation_text": "same obligation",
        "canonical_obligation_source": "semantic_observation.source_atom",
        "canonical_obligation_confidence": 1.0,
        "semantic_role_current": "requirement_candidate",
        "semantic_observation_id": f"obs-{rid}",
        "requirement_type": "other",
        "mandatory": True,
        "priority": "high",
        "requirement_truth_status": "verified",
        "current_response_contract_status": "no_verified_response",
        "projected_response_status": status,
        "projected_reason": "partial",
        "review_origin": "recall",
        "current_response_evidence_count": 0,
        "current_response_evidence": [],
        "recall_gate_class": "PARTIAL_OBLIGATION_COVERAGE",
        "recall_obligation_atom_coverage": 0.5,
        "recall_title_anchor_coverage": 0.0,
        "recall_requirement_atoms": "a | b",
        "recall_shared_atoms": "a",
        "recall_missing_atoms": "b",
        "recall_missing_hard_atoms": "",
        "recall_evidence_id": "ev1",
        "recall_evidence_source": "source.pdf",
        "recall_evidence_locator": "page 1",
        "recall_candidate_text": "candidate",
    }


def _recommendation(rid: str):
    return {
        "project_id": "p",
        "requirement_id": rid,
        "requirement_title": "A",
        "canonical_obligation_text": "same obligation",
        "canonical_obligation_source": "semantic_observation.source_atom",
        "canonical_obligation_confidence": 1.0,
        "semantic_role_current": "requirement_candidate",
        "semantic_observation_id": f"obs-{rid}",
        "requirement_type": "other",
        "mandatory": True,
        "priority": "high",
        "requirement_truth_status_at_review": "verified",
        "current_response_contract_status": "no_verified_response",
        "projected_response_status": "response_review_partial",
        "projected_reason": "partial",
        "review_origin": "recall",
        "current_response_evidence_count": 0,
        "current_response_evidence": [],
        "evidence_id": "ev1",
        "evidence_source": "source.pdf",
        "evidence_locator": "page 1",
        "evidence_text": "candidate",
        "recall_gate_class": "PARTIAL_OBLIGATION_COVERAGE",
        "obligation_atom_coverage": 0.5,
        "title_anchor_coverage": 0.0,
        "requirement_atoms": "a | b",
        "shared_atoms": "a",
        "missing_atoms": "b",
        "missing_hard_atoms": "",
        "candidate_id": f"candidate-{rid}",
        "machine_recommendation": "recommend_reject",
        "machine_confidence": 0.99,
        "machine_rule_id": "guard",
        "machine_rationale": "reason",
        "adjudicator_type": "machine_rule_engine_semantic_hardening_completeness_guard",
        "human_review_created": False,
        "truth_effect_applied": False,
        "persistence_performed": False,
        "source_candidate_id": f"source-{rid}",
        "completeness_scope": None,
        "completeness_guard_applied": False,
    }


def _payload(ids):
    projection = [_projection(rid) for rid in ids]
    recommendations = [_recommendation(rid) for rid in ids]
    return {
        "version": "V28.7.3B2.12.2.2",
        "project_id": "p",
        "status": "PASS_SEMANTIC_HARDENING_READY",
        "current_requirement_count_before_semantic_gate": len(ids),
        "semantic_eligible_requirement_count": len(ids),
        "semantic_excluded_no_domain_count": 0,
        "semantic_unknown_count": 0,
        "canonical_identity_collision_count": 0,
        "queue_count": len(ids),
        "human_review_created": False,
        "truth_changed": False,
        "persistence_performed": False,
        "cutover_approved": False,
        "recommendation_rows": recommendations,
        "semantic_excluded_rows": [],
        "canonical_identity_collision_rows": [],
        "projection_rows": projection,
    }


def _pipeline_contract():
    return {
        "normal_pipeline_uses_h31": True,
        "promotion_version": "V28.7.2C0.2.4H3.1.3P1",
    }


def test_control_exact_match_passes():
    baseline = _payload(["a", "b"])
    current = _payload(["a", "b"])
    result = compare_response_projection_integrity(
        project_id="p",
        baseline=baseline,
        current=current,
        supersession_verification=None,
        supersession_run=None,
        read_mode="shadow_compare",
        pipeline_contract=_pipeline_contract(),
    )
    assert result["status"] == "PASS_CONTROL_NO_DOWNSTREAM_DRIFT"
    assert result["all_checks_pass"] is True


def test_post_supersession_exact_duplicate_removal_passes():
    baseline = _payload(["old", "survivor", "other"])
    baseline["canonical_identity_collision_count"] = 1
    baseline["status"] = "PASS_SEMANTIC_HARDENING_WITH_IDENTITY_COLLISIONS"
    baseline["canonical_identity_collision_rows"] = [{
        "requirement_ids": ["old", "survivor"],
        "canonical_obligation_text": "same obligation",
    }]

    # Old/survivor response semantics are equal, but identity provenance may differ.
    baseline["projection_rows"][0]["title"] = "truncated"
    baseline["projection_rows"][0]["canonical_obligation_source"] = "current_evidence.source_clause"
    baseline["projection_rows"][0]["canonical_obligation_confidence"] = 0.995
    baseline["projection_rows"][0]["semantic_observation_id"] = "obs-old"
    baseline["projection_rows"][0]["requirement_type"] = "deliverable"
    baseline["projection_rows"][0]["mandatory"] = False

    baseline["recommendation_rows"][0]["requirement_title"] = "truncated"
    baseline["recommendation_rows"][0]["canonical_obligation_source"] = "current_evidence.source_clause"
    baseline["recommendation_rows"][0]["canonical_obligation_confidence"] = 0.995
    baseline["recommendation_rows"][0]["semantic_observation_id"] = "obs-old"
    baseline["recommendation_rows"][0]["requirement_type"] = "deliverable"
    baseline["recommendation_rows"][0]["mandatory"] = False

    current = _payload(["survivor", "other"])

    verification = {
        "status": "PASS_POST_TRANSACTION_VERIFICATION",
        "all_checks_pass": True,
        "survivor_requirement_id": "survivor",
        "superseded_requirement_ids": ["old"],
        "response_truth_changed": False,
        "checks": {
            "governance_lineage_complete": True,
            "knowledge_entity_lineage_complete": True,
            "historical_evidence_count_preserved": True,
            "historical_semantic_observation_count_preserved": True,
            "all_legacy_aliases_uniquely_resolve_to_survivor": True,
        },
    }
    run = {
        "id": "run1",
        "status": "completed",
        "pipeline_version": "V28.7.3B2.12.5.4",
        "metadata": {
            "project_id": "p",
            "survivor_requirement_id": "survivor",
            "superseded_requirement_ids": ["old"],
        },
    }

    result = compare_response_projection_integrity(
        project_id="p",
        baseline=baseline,
        current=current,
        supersession_verification=verification,
        supersession_run=run,
        read_mode="shadow_compare",
        pipeline_contract=_pipeline_contract(),
    )
    assert result["status"] == "PASS_POST_SUPERSESSION_RESPONSE_INTEGRITY"
    assert result["all_checks_pass"] is True
    assert result["current"]["current_requirement_count"] == 2
    assert result["expected_after_supersession"]["current_requirement_count"] == 2


def test_unexplained_survivor_drift_blocks():
    baseline = _payload(["old", "survivor"])
    baseline["canonical_identity_collision_count"] = 1
    baseline["canonical_identity_collision_rows"] = [{
        "requirement_ids": ["old", "survivor"],
    }]
    current = _payload(["survivor"])
    current["projection_rows"][0]["projected_response_status"] = "verified_response"

    verification = {
        "status": "PASS_POST_TRANSACTION_VERIFICATION",
        "all_checks_pass": True,
        "survivor_requirement_id": "survivor",
        "superseded_requirement_ids": ["old"],
        "response_truth_changed": False,
        "checks": {
            "governance_lineage_complete": True,
            "knowledge_entity_lineage_complete": True,
            "historical_evidence_count_preserved": True,
            "historical_semantic_observation_count_preserved": True,
            "all_legacy_aliases_uniquely_resolve_to_survivor": True,
        },
    }
    run = {
        "id": "run1",
        "status": "completed",
        "pipeline_version": "V28.7.3B2.12.5.4",
        "metadata": {"project_id": "p"},
    }

    result = compare_response_projection_integrity(
        project_id="p",
        baseline=baseline,
        current=current,
        supersession_verification=verification,
        supersession_run=run,
        read_mode="shadow_compare",
        pipeline_contract=_pipeline_contract(),
    )
    assert result["status"] == "BLOCKED_RESPONSE_IMPACT_SHADOW"
    assert result["all_checks_pass"] is False
    assert result["mismatch_rows"]


def test_module_is_read_only():
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "project_requirement_response_truth_impact_shadow.py"
    ).read_text(encoding="utf-8")
    assert ".insert(" not in source
    assert ".delete(" not in source
    assert ".rpc(" not in source
    assert source.count(".update(") == 1
    assert "common_checks.update(" in source
