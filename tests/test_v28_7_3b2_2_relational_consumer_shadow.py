from __future__ import annotations

from project_requirement_compatibility import build_requirement_compatibility_from_rows
from project_requirement_relational_shadow import (
    build_domain_relational_shadow_snapshot,
    compare_relational_shadow_outputs,
)


def _domain(domain_id="d1", legacy_id="l1", title="Req"):
    return {
        "id": domain_id,
        "entity_id": f"e-{domain_id}",
        "legacy_source_id": legacy_id,
        "title": title,
        "description": title,
        "requirement_type": "deliverable",
        "mandatory": False,
        "priority": "high",
        "truth_state": "verified",
    }


def _legacy_req(legacy_id="l1", title="Req"):
    return {
        "id": legacy_id,
        "title": title,
        "description": title,
        "requirement_type": "deliverable",
        "mandatory": False,
        "priority": "high",
        "adherence_status": "not_assessed",
    }


def _link(link_id="b1", req_id="l1", item_id="i1", status="suggested"):
    return {
        "id": link_id,
        "requirement_id": req_id,
        "memory_item_id": item_id,
        "link_status": status,
        "adherence_status": "not_assessed",
        "evidence": None,
    }


def _compat(domain_rows=None, legacy_rows=None, links=None, occurrences=None):
    return build_requirement_compatibility_from_rows(
        project_id="p1",
        current_domain_rows=domain_rows or [_domain()],
        legacy_requirement_rows=legacy_rows or [_legacy_req()],
        occurrence_rows=occurrences or [],
        legacy_link_rows=links or [_link()],
    )


def _intel(req_id="l1", briefing="Relacionada, ainda não avaliada", matches=None,
           gaps=0, unconsolidated=0):
    return {
        "matrix": [{
            "item_id": "i1",
            "Item apresentado": "Item",
            "Briefing": briefing,
        }],
        "unified": {
            "briefing_matches": [
                {"requirement_id": value}
                for value in (matches if matches is not None else [req_id])
            ]
        },
        "discrepancies": {
            "briefing_gaps": [{} for _ in range(gaps)],
            "briefing_evidence_unconsolidated": [{} for _ in range(unconsolidated)],
        },
    }


def test_shadow_replaces_active_requirement_id_only():
    compat = _compat()
    legacy = {
        "briefing_requirements": [_legacy_req()],
        "briefing_links": [_link()],
        "memory_items": [{"id": "i1"}],
        "intelligence_snapshots": [{"id": "old"}],
    }
    shadow = build_domain_relational_shadow_snapshot(
        legacy,
        domain_requirement_rows=[_domain()],
        compatibility=compat,
    )
    assert legacy["briefing_links"][0]["requirement_id"] == "l1"
    assert shadow["briefing_links"][0]["requirement_id"] == "d1"
    assert shadow["briefing_requirements"][0]["id"] == "d1"
    assert shadow["intelligence_snapshots"] == []


def test_rejected_link_is_not_forced_through_mapping():
    links = [_link(status="rejected")]
    compat = _compat(links=links)
    legacy = {
        "briefing_requirements": [_legacy_req()],
        "briefing_links": links,
        "memory_items": [{"id": "i1"}],
    }
    shadow = build_domain_relational_shadow_snapshot(
        legacy,
        domain_requirement_rows=[_domain()],
        compatibility=compat,
    )
    assert shadow["briefing_links"][0]["requirement_id"] == "l1"


def test_same_relations_pass():
    compat = _compat()
    legacy = {
        "briefing_requirements": [_legacy_req()],
        "briefing_links": [_link()],
        "memory_items": [{"id": "i1"}],
    }
    shadow = build_domain_relational_shadow_snapshot(
        legacy,
        domain_requirement_rows=[_domain()],
        compatibility=compat,
    )
    result = compare_relational_shadow_outputs(
        project_id="p1",
        legacy_snapshot=legacy,
        domain_shadow_snapshot=shadow,
        legacy_intelligence=_intel("l1"),
        domain_intelligence=_intel("d1"),
        compatibility=compat,
    )
    assert result.status == "PASS"
    assert result.matrix_briefing_drift_count == 0
    assert result.active_link_signature_drift is False


def test_matrix_briefing_change_blocks():
    compat = _compat()
    legacy = {
        "briefing_requirements": [_legacy_req()],
        "briefing_links": [_link()],
        "memory_items": [{"id": "i1"}],
    }
    shadow = build_domain_relational_shadow_snapshot(
        legacy,
        domain_requirement_rows=[_domain()],
        compatibility=compat,
    )
    result = compare_relational_shadow_outputs(
        project_id="p1",
        legacy_snapshot=legacy,
        domain_shadow_snapshot=shadow,
        legacy_intelligence=_intel("l1", "Relacionada"),
        domain_intelligence=_intel("d1", "Sem demanda relacionada"),
        compatibility=compat,
    )
    assert result.status == "BLOCKED"
    assert "MATRIX_BRIEFING_RELATION_DRIFT" in result.hard_blockers


def test_mapped_unified_match_loss_is_observation_not_hard_blocker():
    compat = _compat()
    legacy = {
        "briefing_requirements": [_legacy_req()],
        "briefing_links": [_link()],
        "memory_items": [{"id": "i1"}],
    }
    shadow = build_domain_relational_shadow_snapshot(
        legacy,
        domain_requirement_rows=[_domain()],
        compatibility=compat,
    )
    result = compare_relational_shadow_outputs(
        project_id="p1",
        legacy_snapshot=legacy,
        domain_shadow_snapshot=shadow,
        legacy_intelligence=_intel("l1", matches=["l1"]),
        domain_intelligence=_intel("d1", matches=[]),
        compatibility=compat,
    )
    assert result.status == "PASS_WITH_OBSERVATION"
    assert result.mapped_legacy_matches_missing_in_domain == ("d1",)


def test_domain_additional_match_is_observation():
    domain_rows = [_domain("d1", "l1"), _domain("d2", None, "Domain only")]
    compat = _compat(domain_rows=domain_rows)
    legacy = {
        "briefing_requirements": [_legacy_req()],
        "briefing_links": [_link()],
        "memory_items": [{"id": "i1"}],
    }
    shadow = build_domain_relational_shadow_snapshot(
        legacy,
        domain_requirement_rows=domain_rows,
        compatibility=compat,
    )
    result = compare_relational_shadow_outputs(
        project_id="p1",
        legacy_snapshot=legacy,
        domain_shadow_snapshot=shadow,
        legacy_intelligence=_intel("l1", matches=["l1"]),
        domain_intelligence=_intel("d1", matches=["d1", "d2"]),
        compatibility=compat,
    )
    assert result.status == "PASS_WITH_OBSERVATION"
    assert result.domain_unified_additions == ("d2",)


def test_expected_gap_cardinality_difference_is_observation():
    compat = _compat()
    legacy = {
        "briefing_requirements": [_legacy_req()],
        "briefing_links": [_link()],
        "memory_items": [{"id": "i1"}],
    }
    shadow = build_domain_relational_shadow_snapshot(
        legacy,
        domain_requirement_rows=[_domain()],
        compatibility=compat,
    )
    result = compare_relational_shadow_outputs(
        project_id="p1",
        legacy_snapshot=legacy,
        domain_shadow_snapshot=shadow,
        legacy_intelligence=_intel("l1", gaps=2),
        domain_intelligence=_intel("d1", gaps=4),
        compatibility=compat,
    )
    assert result.status == "PASS_WITH_OBSERVATION"
    assert "EXPECTED_REQUIREMENT_CARDINALITY_EFFECT" in result.observations


def test_orphan_domain_item_blocks():
    compat = _compat()
    legacy = {
        "briefing_requirements": [_legacy_req()],
        "briefing_links": [_link()],
        "memory_items": [{"id": "i1"}],
    }
    shadow = build_domain_relational_shadow_snapshot(
        legacy,
        domain_requirement_rows=[_domain()],
        compatibility=compat,
    )
    shadow["memory_items"] = []
    result = compare_relational_shadow_outputs(
        project_id="p1",
        legacy_snapshot=legacy,
        domain_shadow_snapshot=shadow,
        legacy_intelligence=_intel("l1"),
        domain_intelligence=_intel("d1"),
        compatibility=compat,
    )
    assert result.status == "BLOCKED"
    assert "ORPHAN_DOMAIN_LINK" in result.hard_blockers
