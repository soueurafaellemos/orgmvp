from __future__ import annotations

from project_requirement_compatibility import build_requirement_compatibility_from_rows
from project_requirement_unified_reconciliation import (
    reconcile_unified_requirement_sets,
)


def _legacy(req_id, title=None):
    return {
        "id": req_id,
        "title": title or req_id,
        "requirement_type": "deliverable",
        "mandatory": False,
        "priority": "high",
        "adherence_status": "not_assessed",
    }


def _domain(req_id, legacy_id=None, title=None):
    return {
        "id": req_id,
        "entity_id": f"e-{req_id}",
        "legacy_source_id": legacy_id,
        "title": title or req_id,
        "requirement_type": "deliverable",
        "mandatory": False,
        "priority": "high",
        "truth_state": "verified",
        "has_current_evidence": True,
        "has_direct_domain_evidence": True,
    }


def _match(req_id, evidence_id, score=0.8):
    return {
        "requirement_id": req_id,
        "requirement_title": req_id,
        "score": score,
        "status": "evidence_found",
        "evidence": {
            "evidence_id": evidence_id,
            "source_name": "proposal.pdf",
            "locator_text": "slide 10",
            "text": f"evidence for {req_id}",
        },
    }


def _compat(domain_rows, legacy_rows, links=None):
    return build_requirement_compatibility_from_rows(
        project_id="p1",
        current_domain_rows=domain_rows,
        legacy_requirement_rows=legacy_rows,
        occurrence_rows=[],
        legacy_link_rows=links or [],
    )


def test_mapped_match_reproduced_is_not_blocker():
    legacy_rows = [_legacy("l1")]
    domain_rows = [_domain("d1", "l1")]
    compat = _compat(domain_rows, legacy_rows)
    result = reconcile_unified_requirement_sets(
        project_id="p1",
        legacy_requirement_rows=legacy_rows,
        domain_requirement_rows=domain_rows,
        legacy_link_rows=[],
        legacy_unified={"briefing_matches": [_match("l1", "ev1")]},
        domain_unified={"briefing_matches": [_match("d1", "ev1")]},
        compatibility=compat,
    )
    assert result.status == "PASS"
    assert result.mapped_legacy_missing_in_domain_count == 0
    assert result.mapped_both_match_count == 1


def test_mapped_legacy_match_missing_in_domain_blocks_calibration():
    legacy_rows = [_legacy("l1")]
    domain_rows = [_domain("d1", "l1")]
    compat = _compat(domain_rows, legacy_rows)
    result = reconcile_unified_requirement_sets(
        project_id="p1",
        legacy_requirement_rows=legacy_rows,
        domain_requirement_rows=domain_rows,
        legacy_link_rows=[],
        legacy_unified={"briefing_matches": [_match("l1", "ev1")]},
        domain_unified={"briefing_matches": []},
        compatibility=compat,
    )
    assert result.status == "BLOCKED_CALIBRATION"
    assert result.mapped_legacy_missing_in_domain_count == 1


def test_legacy_match_without_alias_is_reconciliation_not_matcher_blocker():
    legacy_rows = [_legacy("l1"), _legacy("l2")]
    domain_rows = [_domain("d1", "l1")]
    compat = _compat(domain_rows, legacy_rows)
    result = reconcile_unified_requirement_sets(
        project_id="p1",
        legacy_requirement_rows=legacy_rows,
        domain_requirement_rows=domain_rows,
        legacy_link_rows=[],
        legacy_unified={
            "briefing_matches": [_match("l1", "ev1"), _match("l2", "ev2")]
        },
        domain_unified={"briefing_matches": [_match("d1", "ev1")]},
        compatibility=compat,
    )
    assert result.status == "RECONCILIATION_REQUIRED"
    assert result.legacy_match_without_domain_alias_count == 1
    row = next(
        row for row in result.detail_rows
        if row["finding_type"] == "legacy_match_without_current_domain_alias"
    )
    assert row["legacy_requirement_id"] == "l2"


def test_domain_only_match_is_reconciliation_required():
    legacy_rows = [_legacy("l1")]
    domain_rows = [_domain("d1", "l1"), _domain("d2", None)]
    compat = _compat(domain_rows, legacy_rows)
    result = reconcile_unified_requirement_sets(
        project_id="p1",
        legacy_requirement_rows=legacy_rows,
        domain_requirement_rows=domain_rows,
        legacy_link_rows=[],
        legacy_unified={"briefing_matches": [_match("l1", "ev1")]},
        domain_unified={
            "briefing_matches": [_match("d1", "ev1"), _match("d2", "ev2")]
        },
        compatibility=compat,
    )
    assert result.status == "RECONCILIATION_REQUIRED"
    assert result.domain_match_without_legacy_alias_count == 1


def test_different_evidence_for_same_mapped_match_is_observation():
    legacy_rows = [_legacy("l1")]
    domain_rows = [_domain("d1", "l1")]
    compat = _compat(domain_rows, legacy_rows)
    result = reconcile_unified_requirement_sets(
        project_id="p1",
        legacy_requirement_rows=legacy_rows,
        domain_requirement_rows=domain_rows,
        legacy_link_rows=[],
        legacy_unified={"briefing_matches": [_match("l1", "ev1")]},
        domain_unified={"briefing_matches": [_match("d1", "ev2")]},
        compatibility=compat,
    )
    assert result.status == "PASS_WITH_OBSERVATION"
    assert result.mapped_different_evidence_count == 1


def test_active_link_count_is_exposed_on_unaliased_legacy_finding():
    legacy_rows = [_legacy("l1"), _legacy("l2")]
    domain_rows = [_domain("d1", "l1")]
    compat = _compat(domain_rows, legacy_rows)
    links = [{
        "id": "b1",
        "requirement_id": "l2",
        "memory_item_id": "i1",
        "link_status": "suggested",
    }]
    result = reconcile_unified_requirement_sets(
        project_id="p1",
        legacy_requirement_rows=legacy_rows,
        domain_requirement_rows=domain_rows,
        legacy_link_rows=links,
        legacy_unified={"briefing_matches": [_match("l2", "ev2")]},
        domain_unified={"briefing_matches": []},
        compatibility=compat,
    )
    row = next(
        row for row in result.detail_rows
        if row["finding_type"] == "legacy_match_without_current_domain_alias"
    )
    assert row["legacy_active_link_count"] == 1
