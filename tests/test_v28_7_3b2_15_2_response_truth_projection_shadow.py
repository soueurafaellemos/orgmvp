from project_requirement_response_truth_projection_shadow import (
    CHAMBINHO,
    JOVI,
    ELIGIBILITY_VERSION,
    SOURCE_PROJECTION_VERSION,
    build_response_truth_ledger_projection_shadow,
)


def _projection_row(rid, evidence_id):
    evidence = []
    if evidence_id:
        evidence = [{
            "verdict": "verified_response",
            "entailment_status": "SUPPORTED_EXPLICIT_ATOM",
            "evidence_id": evidence_id,
            "evidence_locator": "page 1",
            "evidence_text": "supported evidence",
        }]
    return {
        "requirement_id": rid,
        "title": "Requirement",
        "canonical_obligation_text": "Requirement",
        "canonical_obligation_source": "current_evidence.source_clause",
        "canonical_obligation_confidence": 1.0,
        "current_response_contract_status": (
            "verified_response" if evidence_id else "no_verified_response"
        ),
        "projected_response_status": (
            "verified_response" if evidence_id else "no_safely_verified_response"
        ),
        "review_origin": "current_contract" if evidence_id else None,
        "current_response_evidence": evidence,
    }


def _truth_rows(project_id, count, contract_ids):
    rows = []
    for i in range(count):
        rid = f"other-{i}"
        if i < len(contract_ids):
            rid = contract_ids[i]
        rows.append({
            "id": rid,
            "project_id": project_id,
            "entity_id": f"entity-{rid}",
            "truth_state": "verified",
            "lifecycle_status": "active",
        })
    return rows


def _eligibility(project_id, current_count, contract_ids, human_ids):
    rows = []
    for rid in contract_ids:
        rows.append({
            "requirement_id": rid,
            "eligibility_class": "eligible_contract_verified",
        })
    for rid in human_ids:
        rows.append({
            "requirement_id": rid,
            "eligibility_class": "eligible_human_confirmation_only",
        })
    return {
        "version": ELIGIBILITY_VERSION,
        "project_id": project_id,
        "status": "PASS_RESPONSE_TRUTH_ELIGIBILITY_SHADOW",
        "all_checks_pass": True,
        "current_requirement_count": current_count,
        "blocked_count": 0,
        "machine_recommendation_is_truth": False,
        "eligibility_rows": rows,
    }


def _truth_status_rows(project_id, truth_rows):
    return [
        {
            "requirement_id": row["id"],
            "project_id": project_id,
            "response_truth_status": "no_persisted_response_truth",
        }
        for row in truth_rows
    ]


def test_chambinho_exact_projection_passes():
    contract_ids = [
        "cf0516d7-4cf4-49c2-94dd-858dd3ab907c",
        "40433db9-3b46-4d68-9add-18eb5d479ef8",
        "be3b3716-95bc-4689-b646-95cfe872988c",
    ]
    evidence_map = {
        contract_ids[0]: "884f4586-c46a-4624-9fa5-c89f63fc1f2e",
        contract_ids[1]: "7bfc9e2f-1bb6-416e-b9a8-f54034964e47",
        contract_ids[2]: "7bfc9e2f-1bb6-416e-b9a8-f54034964e47",
    }
    truth_rows = _truth_rows(CHAMBINHO, 13, contract_ids)
    source_projection = {
        "version": SOURCE_PROJECTION_VERSION,
        "project_id": CHAMBINHO,
        "projection_rows": [
            _projection_row(rid, evidence_map[rid])
            for rid in contract_ids
        ],
    }
    eligibility = _eligibility(
        CHAMBINHO,
        13,
        contract_ids,
        ["bdbee458-8ba1-45c7-b871-60a604a2971a"],
    )
    result = build_response_truth_ledger_projection_shadow(
        project_id=CHAMBINHO,
        eligibility=eligibility,
        source_projection=source_projection,
        requirement_truth_rows=truth_rows,
        evidence_unit_rows=[
            {"id": "884f4586-c46a-4624-9fa5-c89f63fc1f2e"},
            {"id": "7bfc9e2f-1bb6-416e-b9a8-f54034964e47"},
        ],
        ledger_state={
            "events_count": 0,
            "evidence_count": 0,
            "current_truth_count": 0,
            "truth_status_rows": _truth_status_rows(CHAMBINHO, truth_rows),
        },
    )
    assert result["all_checks_pass"] is True, result["failed_checks"]
    assert result["projected_event_count"] == 3
    assert result["projected_evidence_link_count"] == 3
    assert result["safe_to_write_response_truth"] is False


def test_jovi_control_projects_zero_events():
    truth_rows = _truth_rows(JOVI, 69, [])
    result = build_response_truth_ledger_projection_shadow(
        project_id=JOVI,
        eligibility=_eligibility(
            JOVI,
            69,
            [],
            ["6edad615-e726-5cd4-8db1-0d7bbbbcf610"],
        ),
        source_projection={
            "version": SOURCE_PROJECTION_VERSION,
            "project_id": JOVI,
            "projection_rows": [],
        },
        requirement_truth_rows=truth_rows,
        evidence_unit_rows=[],
        ledger_state={
            "events_count": 0,
            "evidence_count": 0,
            "current_truth_count": 0,
            "truth_status_rows": _truth_status_rows(JOVI, truth_rows),
        },
    )
    assert result["all_checks_pass"] is True, result["failed_checks"]
    assert result["projected_event_count"] == 0
    assert result["human_confirmation_candidate_count"] == 1


def test_existing_ledger_row_blocks_projection():
    contract_ids = [
        "cf0516d7-4cf4-49c2-94dd-858dd3ab907c",
        "40433db9-3b46-4d68-9add-18eb5d479ef8",
        "be3b3716-95bc-4689-b646-95cfe872988c",
    ]
    evidence_map = {
        contract_ids[0]: "884f4586-c46a-4624-9fa5-c89f63fc1f2e",
        contract_ids[1]: "7bfc9e2f-1bb6-416e-b9a8-f54034964e47",
        contract_ids[2]: "7bfc9e2f-1bb6-416e-b9a8-f54034964e47",
    }
    truth_rows = _truth_rows(CHAMBINHO, 13, contract_ids)
    result = build_response_truth_ledger_projection_shadow(
        project_id=CHAMBINHO,
        eligibility=_eligibility(
            CHAMBINHO,
            13,
            contract_ids,
            ["bdbee458-8ba1-45c7-b871-60a604a2971a"],
        ),
        source_projection={
            "version": SOURCE_PROJECTION_VERSION,
            "project_id": CHAMBINHO,
            "projection_rows": [
                _projection_row(rid, evidence_map[rid])
                for rid in contract_ids
            ],
        },
        requirement_truth_rows=truth_rows,
        evidence_unit_rows=[
            {"id": "884f4586-c46a-4624-9fa5-c89f63fc1f2e"},
            {"id": "7bfc9e2f-1bb6-416e-b9a8-f54034964e47"},
        ],
        ledger_state={
            "events_count": 1,
            "evidence_count": 0,
            "current_truth_count": 0,
            "truth_status_rows": _truth_status_rows(CHAMBINHO, truth_rows),
        },
    )
    assert result["all_checks_pass"] is False
    assert "ledger_events_empty_before_projection" in result["failed_checks"]


def test_evidence_drift_blocks_projection():
    contract_ids = [
        "cf0516d7-4cf4-49c2-94dd-858dd3ab907c",
        "40433db9-3b46-4d68-9add-18eb5d479ef8",
        "be3b3716-95bc-4689-b646-95cfe872988c",
    ]
    truth_rows = _truth_rows(CHAMBINHO, 13, contract_ids)
    source_projection = {
        "version": SOURCE_PROJECTION_VERSION,
        "project_id": CHAMBINHO,
        "projection_rows": [
            _projection_row(contract_ids[0], "wrong-evidence"),
            _projection_row(
                contract_ids[1],
                "7bfc9e2f-1bb6-416e-b9a8-f54034964e47",
            ),
            _projection_row(
                contract_ids[2],
                "7bfc9e2f-1bb6-416e-b9a8-f54034964e47",
            ),
        ],
    }
    result = build_response_truth_ledger_projection_shadow(
        project_id=CHAMBINHO,
        eligibility=_eligibility(
            CHAMBINHO,
            13,
            contract_ids,
            ["bdbee458-8ba1-45c7-b871-60a604a2971a"],
        ),
        source_projection=source_projection,
        requirement_truth_rows=truth_rows,
        evidence_unit_rows=[
            {"id": "wrong-evidence"},
            {"id": "7bfc9e2f-1bb6-416e-b9a8-f54034964e47"},
        ],
        ledger_state={
            "events_count": 0,
            "evidence_count": 0,
            "current_truth_count": 0,
            "truth_status_rows": _truth_status_rows(CHAMBINHO, truth_rows),
        },
    )
    assert result["all_checks_pass"] is False
    assert "golden_evidence_identity_sets_unchanged" in result["failed_checks"]


def test_module_is_read_only():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "project_requirement_response_truth_projection_shadow.py"
    ).read_text(encoding="utf-8")
    assert ".insert(" not in source
    assert ".delete(" not in source
    assert ".rpc(" not in source
    assert source.count(".update(") == 1
    assert "missing_evidence_units.update(" in source
