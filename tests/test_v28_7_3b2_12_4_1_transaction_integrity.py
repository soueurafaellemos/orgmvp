from project_requirement_identity_supersession_dry_run import (
    _coalesce_evidence_actions,
    _entity_integrity_findings,
    occurrence_hash,
)


def test_occurrence_hash_changes_with_requirement_identity():
    assert occurrence_hash("p", "old", "e", "requirement") != occurrence_hash(
        "p", "new", "e", "requirement"
    )


def test_missing_governance_blocks_transaction_integrity():
    findings, _, _ = _entity_integrity_findings(
        survivor_requirement_id="survivor",
        survivor_entity_id="se",
        superseded_pairs=[("old", "oe")],
        governance_rows=[],
        knowledge_rows=[
            {"id": "se", "domain_table": "project_requirements", "domain_id": "survivor"},
            {"id": "oe", "domain_table": "project_requirements", "domain_id": "old"},
        ],
    )
    assert "governance_row_count:survivor:0" in findings
    assert "governance_row_count:old:0" in findings


def test_eight_historical_occurrence_links_coalesce_to_one_action():
    old_links = [
        {
            "id": f"old-{i}",
            "object_entity_id": "oe",
            "domain_table": "project_requirements",
            "domain_id": "old",
            "evidence_unit_id": "ev",
            "link_role": "occurrence",
            "context": {"requirement_occurrence_id": "occ-old"},
        }
        for i in range(8)
    ]
    actions, raw_count, coalesced_count, findings = _coalesce_evidence_actions(
        survivor_id="survivor",
        survivor_entity_id="se",
        superseded_ids={"old"},
        superseded_entity_ids={"oe"},
        evidence_rows=old_links,
        target_occurrence_by_source={"occ-old": "occ-survivor"},
    )
    assert raw_count == 8
    assert coalesced_count == 1
    assert findings == []
    assert actions[0]["action"] == "insert_single_survivor_evidence_link"
    assert len(actions[0]["coalesced_source_evidence_link_ids"]) == 8
    assert actions[0]["target_requirement_occurrence_id"] == "occ-survivor"


def test_existing_survivor_evidence_is_reused_not_duplicated():
    rows = [
        {
            "id": "old-1",
            "object_entity_id": "oe",
            "domain_table": "project_requirements",
            "domain_id": "old",
            "evidence_unit_id": "ev",
            "link_role": "occurrence",
            "context": {"requirement_occurrence_id": "occ-old"},
        },
        {
            "id": "survivor-existing",
            "object_entity_id": "se",
            "domain_table": "project_requirements",
            "domain_id": "survivor",
            "evidence_unit_id": "ev",
            "link_role": "occurrence",
            "context": {"requirement_occurrence_id": "occ-survivor"},
        },
    ]
    actions, _, count, findings = _coalesce_evidence_actions(
        survivor_id="survivor",
        survivor_entity_id="se",
        superseded_ids={"old"},
        superseded_entity_ids={"oe"},
        evidence_rows=rows,
        target_occurrence_by_source={"occ-old": "occ-survivor"},
    )
    assert count == 1
    assert findings == []
    assert actions[0]["action"] == "reuse_existing_survivor_evidence_link"
    assert actions[0]["existing_survivor_evidence_link_ids"] == ["survivor-existing"]
