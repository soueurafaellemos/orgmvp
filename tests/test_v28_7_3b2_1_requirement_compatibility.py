from __future__ import annotations

from project_requirement_compatibility import (
    build_requirement_compatibility_from_rows,
    compatibility_alias_maps,
    shadow_compatible_snapshot,
)


def _domain(domain_id, legacy_id, title="Requirement", truth="verified"):
    return {
        "id": domain_id,
        "entity_id": f"entity-{domain_id}",
        "legacy_source_id": legacy_id,
        "title": title,
        "requirement_type": "deliverable",
        "mandatory": False,
        "priority": "high",
        "truth_state": truth,
    }


def _legacy(legacy_id, title="Requirement"):
    return {"id": legacy_id, "title": title, "requirement_type": "deliverable"}


def _link(link_id, legacy_id, item_id, status="suggested"):
    return {
        "id": link_id,
        "requirement_id": legacy_id,
        "memory_item_id": item_id,
        "link_status": status,
        "adherence_status": "not_assessed",
    }


def test_two_links_can_share_one_unique_domain_requirement():
    report = build_requirement_compatibility_from_rows(
        project_id="p1",
        current_domain_rows=[_domain("d1", "l1", "Press kit")],
        legacy_requirement_rows=[_legacy("l1", "Press kit")],
        occurrence_rows=[{
            "requirement_id": "d1",
            "legacy_requirement_id": "l1",
            "lifecycle_status": "active",
        }],
        legacy_link_rows=[
            _link("b1", "l1", "i1"),
            _link("b2", "l1", "i2"),
        ],
    )
    assert report.pass_data_bridge is True
    assert report.active_link_count == 2
    assert report.resolved_active_link_count == 2
    assert {row.domain_requirement_id for row in report.links} == {"d1"}
    assert set(report.links[0].bridge_sources) == {
        "legacy_source_id",
        "requirement_occurrence",
    }


def test_active_unmapped_link_blocks():
    report = build_requirement_compatibility_from_rows(
        project_id="p1",
        current_domain_rows=[_domain("d1", "l1")],
        legacy_requirement_rows=[_legacy("l1"), _legacy("l2")],
        occurrence_rows=[],
        legacy_link_rows=[_link("b1", "l2", "i2")],
    )
    assert report.pass_data_bridge is False
    assert report.active_links_unmapped == 1


def test_rejected_unmapped_link_does_not_block():
    report = build_requirement_compatibility_from_rows(
        project_id="p1",
        current_domain_rows=[_domain("d1", "l1")],
        legacy_requirement_rows=[_legacy("l1"), _legacy("l2")],
        occurrence_rows=[],
        legacy_link_rows=[_link("b1", "l2", "i2", status="rejected")],
    )
    assert report.pass_data_bridge is True
    assert report.active_link_count == 0


def test_ambiguous_bridge_blocks_active_link():
    report = build_requirement_compatibility_from_rows(
        project_id="p1",
        current_domain_rows=[
            _domain("d1", "l1"),
            _domain("d2", None),
        ],
        legacy_requirement_rows=[_legacy("l1")],
        occurrence_rows=[{
            "requirement_id": "d2",
            "legacy_requirement_id": "l1",
            "lifecycle_status": "active",
        }],
        legacy_link_rows=[_link("b1", "l1", "i1")],
    )
    assert report.pass_data_bridge is False
    assert report.active_links_ambiguous == 1


def test_non_current_domain_rows_cannot_receive_links():
    report = build_requirement_compatibility_from_rows(
        project_id="p1",
        current_domain_rows=[_domain("d1", "l1", truth="candidate")],
        legacy_requirement_rows=[_legacy("l1")],
        occurrence_rows=[],
        legacy_link_rows=[_link("b1", "l1", "i1")],
    )
    assert report.current_domain_count == 0
    assert report.pass_data_bridge is False


def test_domain_only_requirement_is_allowed():
    report = build_requirement_compatibility_from_rows(
        project_id="p1",
        current_domain_rows=[
            _domain("d1", "l1"),
            _domain("d2", None, "Evidence-only"),
        ],
        legacy_requirement_rows=[_legacy("l1")],
        occurrence_rows=[],
        legacy_link_rows=[_link("b1", "l1", "i1")],
    )
    assert report.pass_data_bridge is True
    assert report.domain_without_legacy_alias_count == 1


def test_alias_maps_are_domain_primary_but_preserve_legacy_alias():
    report = build_requirement_compatibility_from_rows(
        project_id="p1",
        current_domain_rows=[_domain("d1", "l1")],
        legacy_requirement_rows=[_legacy("l1")],
        occurrence_rows=[],
        legacy_link_rows=[_link("b1", "l1", "i1")],
    )
    legacy_to_domain, domain_to_legacy = compatibility_alias_maps(report)
    assert legacy_to_domain == {"l1": "d1"}
    assert domain_to_legacy == {"d1": ("l1",)}


def test_shadow_snapshot_does_not_replace_legacy_fields():
    snapshot = {
        "briefing_requirements": [{"id": "l1", "title": "Legacy"}],
        "briefing_links": [{"id": "b1", "requirement_id": "l1"}],
    }
    report = build_requirement_compatibility_from_rows(
        project_id="p1",
        current_domain_rows=[_domain("d1", "l1")],
        legacy_requirement_rows=[_legacy("l1")],
        occurrence_rows=[],
        legacy_link_rows=[_link("b1", "l1", "i1")],
    )
    decorated = shadow_compatible_snapshot(snapshot, report)
    assert decorated["briefing_requirements"] == snapshot["briefing_requirements"]
    assert decorated["briefing_links"] == snapshot["briefing_links"]
    assert decorated["requirement_compatibility"]["legacy_to_domain"]["l1"] == "d1"
    assert decorated["requirement_compatibility"]["active_links"][0]["domain_requirement_id"] == "d1"
