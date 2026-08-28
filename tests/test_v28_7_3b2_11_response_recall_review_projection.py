from __future__ import annotations

from types import SimpleNamespace

from project_requirement_response_recall_review_projection import (
    build_response_recall_review_projection,
)


def contract_row(rid, status):
    return {
        "requirement_id": rid,
        "title": f"Requirement {rid}",
        "requirement_type": "constraint",
        "mandatory": True,
        "priority": "high",
        "truth_status": "verified",
        "response_contract_status": status,
        "response_evidence_count": 0,
        "response_evidence": [],
    }


def recall_row(rid, cls, coverage=0.0, anchor=0.0):
    return {
        "requirement_id": rid,
        "b210_class": cls,
        "obligation_atom_coverage": coverage,
        "title_anchor_coverage": anchor,
        "requirement_atoms": "a | b",
        "shared_atoms": "a",
        "missing_atoms": "b",
        "missing_hard_atoms": "",
        "evidence_locator": "page 1",
        "candidate_text": "candidate",
    }


def build(contract_rows, recall_rows, semantic=()):
    return build_response_recall_review_projection(
        project_id="p1",
        response_contract=SimpleNamespace(
            project_id="p1",
            requirement_rows=tuple(contract_rows),
            semantic_response_rows=tuple(semantic),
        ),
        obligation_gate=SimpleNamespace(
            project_id="p1",
            detail_rows=tuple(recall_rows),
        ),
    )


def test_existing_verified_is_only_verified_path():
    result = build(
        [contract_row("r1", "verified_response")],
        [recall_row("r1", "HIGH_CONFIDENCE_REVIEW_CANDIDATE", 1.0, 1.0)],
    )
    row = result.requirement_rows[0]
    assert row["projected_response_status"] == "verified_response"
    assert result.verified_response_count == 1


def test_high_confidence_recall_stays_review_only():
    result = build(
        [contract_row("r1", "no_verified_response")],
        [recall_row("r1", "HIGH_CONFIDENCE_REVIEW_CANDIDATE", 1.0, 0.5)],
    )
    row = result.requirement_rows[0]
    assert row["projected_response_status"] == "response_review_high_confidence"
    assert result.verified_response_count == 0
    assert result.high_confidence_review_count == 1


def test_strict_safe_recall_still_stays_review_only():
    result = build(
        [contract_row("r1", "no_verified_response")],
        [recall_row("r1", "STRICT_SAFE_AUTO_PRESERVED", 1.0, 1.0)],
    )
    row = result.requirement_rows[0]
    assert row["projected_response_status"] == "response_review_high_confidence"
    assert result.strict_safe_recall_candidate_count == 1
    assert result.verified_response_count == 0


def test_visual_review_precedes_partial_recall():
    result = build(
        [contract_row("r1", "response_review_visual_or_structured_evidence")],
        [recall_row("r1", "PARTIAL_OBLIGATION_COVERAGE", 0.5, 0.2)],
    )
    assert result.requirement_rows[0]["projected_response_status"] == \
        "response_review_visual_or_structured_evidence"


def test_partial_recall_is_review_partial():
    result = build(
        [contract_row("r1", "no_verified_response")],
        [recall_row("r1", "PARTIAL_OBLIGATION_COVERAGE", 0.5, 0.2)],
    )
    assert result.requirement_rows[0]["projected_response_status"] == \
        "response_review_partial"


def test_false_positive_is_preserved_when_no_better_recall_exists():
    result = build(
        [contract_row("r1", "false_positive_excluded")],
        [recall_row("r1", "NO_CANDIDATE")],
    )
    assert result.requirement_rows[0]["projected_response_status"] == \
        "false_positive_excluded"


def test_high_recall_can_create_review_after_current_false_positive_but_not_verify():
    result = build(
        [contract_row("r1", "false_positive_excluded")],
        [recall_row("r1", "HIGH_CONFIDENCE_REVIEW_CANDIDATE", 1.0, 0.5)],
    )
    row = result.requirement_rows[0]
    assert row["current_response_contract_status"] == "false_positive_excluded"
    assert row["projected_response_status"] == "response_review_high_confidence"
    assert result.verified_response_count == 0


def test_source_role_and_generic_rejections_do_not_create_review():
    result = build(
        [
            contract_row("r1", "no_verified_response"),
            contract_row("r2", "no_verified_response"),
        ],
        [
            recall_row("r1", "REJECT_SOURCE_ROLE_NON_RESPONSE"),
            recall_row("r2", "REJECT_GENERIC_OVERLAP"),
        ],
    )
    assert result.no_safely_verified_response_count == 2
    assert result.source_role_rejected_count == 1
    assert result.generic_overlap_rejected_count == 1


def test_best_recall_candidate_is_selected_by_governed_priority():
    result = build(
        [contract_row("r1", "no_verified_response")],
        [
            recall_row("r1", "PARTIAL_OBLIGATION_COVERAGE", 0.9, 0.7),
            recall_row("r1", "HIGH_CONFIDENCE_REVIEW_CANDIDATE", 0.8, 0.5),
        ],
    )
    row = result.requirement_rows[0]
    assert row["recall_gate_class"] == "HIGH_CONFIDENCE_REVIEW_CANDIDATE"
    assert row["recall_candidate_count"] == 2


def test_semantic_cross_domain_rows_are_preserved_separately():
    semantic = ({
        "legacy_title": "Camera superiority",
        "semantic_response_status": "cross_domain_response_supported",
    },)
    result = build(
        [contract_row("r1", "no_verified_response")],
        [],
        semantic=semantic,
    )
    assert len(result.semantic_response_rows) == 1
    assert result.semantic_response_rows[0]["legacy_title"] == "Camera superiority"
