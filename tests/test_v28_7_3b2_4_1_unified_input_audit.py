from __future__ import annotations

from project_requirement_compatibility import build_requirement_compatibility_from_rows
from project_requirement_unified_input_audit import audit_unified_input_shape


def _legacy(req_id, title, description=""):
    return {
        "id": req_id,
        "title": title,
        "description": description,
        "requirement_type": "deliverable",
    }


def _domain(req_id, title, legacy_id=None, description=""):
    return {
        "id": req_id,
        "entity_id": f"e-{req_id}",
        "legacy_source_id": legacy_id,
        "title": title,
        "description": description,
        "requirement_type": "deliverable",
        "truth_state": "verified",
    }


def _match(req_id, evidence_text, score=0.5):
    return {
        "requirement_id": req_id,
        "score": score,
        "evidence": {
            "evidence_id": f"ev-{req_id}",
            "source_name": "proposal.pdf",
            "locator_text": "page 1",
            "text": evidence_text,
        },
    }


def _compat(domain_rows, legacy_rows):
    return build_requirement_compatibility_from_rows(
        project_id="p1",
        current_domain_rows=domain_rows,
        legacy_requirement_rows=legacy_rows,
        occurrence_rows=[],
        legacy_link_rows=[],
    )


def test_exact_title_counterpart_is_detected_without_creating_alias():
    legacy_rows = [_legacy("l1", "Instagram")]
    domain_rows = [_domain("d1", "Instagram", None)]
    result = audit_unified_input_shape(
        project_id="p1",
        legacy_requirement_rows=legacy_rows,
        domain_requirement_rows=domain_rows,
        legacy_unified={
            "briefing_matches": [_match("l1", "Instagram activation")]
        },
        domain_unified={"briefing_matches": []},
        compatibility=_compat(domain_rows, legacy_rows),
    )
    assert result.legacy_divergent_with_exact_domain_title == 1
    row = result.detail_rows[0]
    assert row["domain_requirement_id"] == "d1"


def test_no_exact_title_remains_semantic_set_review():
    legacy_rows = [_legacy("l1", "Audience")]
    domain_rows = [_domain("d1", "Budget", None)]
    result = audit_unified_input_shape(
        project_id="p1",
        legacy_requirement_rows=legacy_rows,
        domain_requirement_rows=domain_rows,
        legacy_unified={
            "briefing_matches": [_match("l1", "Audience families children")]
        },
        domain_unified={"briefing_matches": []},
        compatibility=_compat(domain_rows, legacy_rows),
    )
    assert result.legacy_divergent_without_exact_domain_title == 1
    assert result.status == "SEMANTIC_SET_REVIEW_REQUIRED"


def test_domain_only_match_is_exposed():
    legacy_rows = []
    domain_rows = [_domain("d1", "Hands on lab", None)]
    result = audit_unified_input_shape(
        project_id="p1",
        legacy_requirement_rows=legacy_rows,
        domain_requirement_rows=domain_rows,
        legacy_unified={"briefing_matches": []},
        domain_unified={
            "briefing_matches": [_match("d1", "JOVI X300 launch", 0.41)]
        },
        compatibility=_compat(domain_rows, legacy_rows),
    )
    assert result.domain_only_match_count == 1
    row = result.detail_rows[0]
    assert row["finding_type"] == "domain_match_without_structural_legacy_alias"


def test_structurally_aliased_legacy_match_is_not_divergent():
    legacy_rows = [_legacy("l1", "Instagram")]
    domain_rows = [_domain("d1", "Instagram", "l1")]
    result = audit_unified_input_shape(
        project_id="p1",
        legacy_requirement_rows=legacy_rows,
        domain_requirement_rows=domain_rows,
        legacy_unified={
            "briefing_matches": [_match("l1", "Instagram activation")]
        },
        domain_unified={
            "briefing_matches": [_match("d1", "Instagram activation")]
        },
        compatibility=_compat(domain_rows, legacy_rows),
    )
    assert result.legacy_divergent_match_count == 0
