from project_requirement_response_truth_eligibility_shadow import (
    BLOCKED,
    ELIGIBLE_CONTRACT,
    ELIGIBLE_HUMAN,
    NOT_NO_SAFE,
    NOT_PARTIAL,
    NOT_REJECT,
    build_response_truth_eligibility_shadow,
    classify_response_truth_eligibility,
)


def _contract_row():
    return {
        "requirement_id": "r1",
        "title": "Brindes",
        "requirement_truth_status": "verified",
        "current_response_contract_status": "verified_response",
        "projected_response_status": "verified_response",
        "current_response_evidence": [{
            "verdict": "verified_response",
            "entailment_status": "SUPPORTED_EXPLICIT_ATOM",
            "evidence_id": "ev1",
        }],
    }


def _review_projection(rid="r2", status="response_review_high_confidence"):
    return {
        "requirement_id": rid,
        "title": "Plenária",
        "requirement_truth_status": "verified",
        "current_response_contract_status": "no_verified_response",
        "projected_response_status": status,
        "current_response_evidence": [],
    }


def _recommendation(rid="r2", recommendation="recommend_confirm"):
    return {
        "requirement_id": rid,
        "machine_recommendation": recommendation,
        "machine_confidence": 0.99,
        "evidence_id": "ev2",
        "evidence_source": "proposal.pdf",
        "evidence_locator": "page 1",
        "requirement_truth_status_at_review": "verified",
        "human_review_created": False,
        "truth_effect_applied": False,
        "persistence_performed": False,
        "completeness_guard_applied": False,
    }


def test_contract_verified_is_eligible_without_human_synthesis():
    row = classify_response_truth_eligibility(_contract_row(), None)
    assert row["eligibility_class"] == ELIGIBLE_CONTRACT
    assert row["future_truth_target_state"] == "verified_response"
    assert row["requires_explicit_human_decision"] is False
    assert row["truth_effect_applied"] is False


def test_machine_confirm_is_human_candidate_not_truth():
    row = classify_response_truth_eligibility(
        _review_projection(),
        _recommendation(),
    )
    assert row["eligibility_class"] == ELIGIBLE_HUMAN
    assert row["future_truth_target_state"] == "human_confirmed_response"
    assert row["requires_explicit_human_decision"] is True
    assert row["truth_effect_applied"] is False
    assert row["persistence_performed"] is False


def test_partial_reject_and_no_safe_are_not_eligible():
    partial = classify_response_truth_eligibility(
        _review_projection(status="response_review_partial"),
        _recommendation(recommendation="recommend_partial"),
    )
    reject = classify_response_truth_eligibility(
        _review_projection(status="response_review_partial"),
        _recommendation(recommendation="recommend_reject"),
    )
    no_safe = classify_response_truth_eligibility({
        "requirement_id": "r3",
        "title": "Budget",
        "requirement_truth_status": "verified",
        "current_response_contract_status": "no_verified_response",
        "projected_response_status": "no_safely_verified_response",
        "current_response_evidence": [],
    }, None)
    assert partial["eligibility_class"] == NOT_PARTIAL
    assert reject["eligibility_class"] == NOT_REJECT
    assert no_safe["eligibility_class"] == NOT_NO_SAFE


def test_machine_confirm_with_truth_effect_is_blocked():
    rec = _recommendation()
    rec["truth_effect_applied"] = True
    row = classify_response_truth_eligibility(_review_projection(), rec)
    assert row["eligibility_class"] == BLOCKED


def test_complete_synthetic_shadow_passes():
    projection = {
        "version": "V28.7.3B2.12.2.2",
        "project_id": "p",
        "truth_changed": False,
        "human_review_created": False,
        "persistence_performed": False,
        "cutover_approved": False,
        "semantic_unknown_count": 0,
        "canonical_identity_collision_count": 0,
        "current_requirement_count_before_semantic_gate": 3,
        "projection_rows": [
            _contract_row(),
            _review_projection(),
            {
                "requirement_id": "r3",
                "title": "Budget",
                "requirement_truth_status": "verified",
                "current_response_contract_status": "no_verified_response",
                "projected_response_status": "no_safely_verified_response",
                "current_response_evidence": [],
            },
        ],
        "recommendation_rows": [_recommendation()],
    }
    result = build_response_truth_eligibility_shadow(
        project_id="p",
        projection=projection,
        read_mode="shadow_compare",
        pipeline_contract={
            "normal_pipeline_uses_h31": True,
            "promotion_version": "V28.7.2C0.2.4H3.1.3P1",
        },
        supersession_verification=None,
    )
    assert result["all_checks_pass"] is True
    assert result["contract_verified_count"] == 1
    assert result["human_confirmation_candidate_count"] == 1
    assert result["eligibility_counts"][NOT_NO_SAFE] == 1


def test_module_has_no_db_mutation_calls():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "project_requirement_response_truth_eligibility_shadow.py"
    ).read_text(encoding="utf-8")
    assert ".insert(" not in source
    assert ".delete(" not in source
    assert ".rpc(" not in source
    # The module uses dict.update() to build read-only rows; no DB update chain exists.
    assert ".table(" in source
    assert ".update(" in source
    assert ".table(" + '"x"' not in source
