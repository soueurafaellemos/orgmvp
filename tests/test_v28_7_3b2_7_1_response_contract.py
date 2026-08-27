from __future__ import annotations

from types import SimpleNamespace

from project_requirement_response_contract_canary import (
    build_response_contract_canary,
)


def _req(req_id, title):
    return {
        "id": req_id,
        "truth_state": "verified",
        "requirement_name": title,
        "description": title,
        "requirement_type": "deliverable",
        "mandatory": False,
        "priority": "high",
    }


def _ent_row(
    domain_id,
    title,
    status,
    disposition="requirement_owned_response",
):
    return {
        "side": "legacy",
        "legacy_requirement_id": f"legacy-{domain_id}",
        "legacy_title": title,
        "domain_requirement_id": domain_id,
        "domain_title": title,
        "contract_disposition": disposition,
        "ownership_domain": "requirements",
        "ownership_labels": title,
        "ownership_review_required": False,
        "entailment_status": status,
        "evidence_id": "ev1",
        "evidence_locator": "page 1",
        "evidence_text": "evidence",
    }


def test_supported_requirement_becomes_verified_response():
    entail = SimpleNamespace(detail_rows=(
        _ent_row("d1", "Brindes", "SUPPORTED_EXPLICIT_ATOM"),
    ))
    result = build_response_contract_canary(
        project_id="p1",
        current_domain_requirement_rows=[_req("d1", "Brindes")],
        entailment_result=entail,
    )
    assert result.verified_response_count == 1
    assert result.requirement_rows[0]["response_contract_status"] == \
        "verified_response"


def test_heading_only_is_review_not_false_positive():
    entail = SimpleNamespace(detail_rows=(
        _ent_row(
            "d1",
            "Item para ser incluído no press kit / Seeding",
            "REVIEW_HEADING_ONLY",
        ),
    ))
    result = build_response_contract_canary(
        project_id="p1",
        current_domain_requirement_rows=[
            _req("d1", "Item para ser incluído no press kit / Seeding")
        ],
        entailment_result=entail,
    )
    assert result.response_review_count == 1
    assert result.false_positive_excluded_count == 0
    assert result.status == "PASS_WITH_RESPONSE_REVIEW"


def test_substantive_no_anchor_is_excluded_false_positive():
    entail = SimpleNamespace(detail_rows=(
        _ent_row(
            "d1",
            "Restrição de verba e estrutura",
            "REVIEW_NO_TITLE_ANCHOR",
        ),
    ))
    result = build_response_contract_canary(
        project_id="p1",
        current_domain_requirement_rows=[
            _req("d1", "Restrição de verba e estrutura")
        ],
        entailment_result=entail,
    )
    assert result.false_positive_excluded_count == 1
    assert result.status == "BLOCKED_CURRENT_RESPONSE_FALSE_POSITIVE"


def test_no_match_is_no_verified_response_not_failure_claim():
    entail = SimpleNamespace(detail_rows=())
    result = build_response_contract_canary(
        project_id="p1",
        current_domain_requirement_rows=[_req("d1", "Budget")],
        entailment_result=entail,
    )
    assert result.no_verified_response_count == 1
    assert result.requirement_rows[0]["response_contract_status"] == \
        "no_verified_response"


def test_cross_domain_supported_is_not_requirement_compliance():
    row = _ent_row(
        "",
        "Camera superiority",
        "SUPPORTED_CANONICAL_ANCHORS",
        disposition="cross_domain_owned_same_evidence",
    )
    row["domain_requirement_id"] = None
    row["ownership_domain"] = "journey"
    row["ownership_labels"] = "PRODUCT REVEAL"
    entail = SimpleNamespace(detail_rows=(row,))
    result = build_response_contract_canary(
        project_id="p1",
        current_domain_requirement_rows=[],
        entailment_result=entail,
    )
    assert result.cross_domain_supported_count == 1
    assert result.total_requirements == 0


from project_requirement_response_contract_canary import (
    _only_current_truth_requirements,
)


def test_b271_denominator_excludes_legacy_unverified_and_historical():
    rows = [
        {"id": "v1", "truth_state": "verified"},
        {"id": "h1", "truth_state": "human_confirmed"},
        {"id": "l1", "truth_state": "legacy_unverified"},
        {"id": "x1", "truth_state": "historical"},
        {"id": "n1", "truth_state": None},
    ]
    current = _only_current_truth_requirements(rows)
    assert [row["id"] for row in current] == ["v1", "h1"]


def test_b271_denominator_does_not_inflate_contract_total():
    entail = SimpleNamespace(detail_rows=())
    rows = [
        _req("v1", "Verified Requirement"),
        {
            **_req("l1", "Legacy Requirement"),
            "truth_state": "legacy_unverified",
        },
        {
            **_req("x1", "Historical Requirement"),
            "truth_state": "historical",
        },
    ]
    current = _only_current_truth_requirements(rows)
    result = build_response_contract_canary(
        project_id="p1",
        current_domain_requirement_rows=current,
        entailment_result=entail,
    )
    assert result.total_requirements == 1
    assert result.no_verified_response_count == 1
