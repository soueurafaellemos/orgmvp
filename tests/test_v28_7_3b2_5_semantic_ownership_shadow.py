from __future__ import annotations
from types import SimpleNamespace

from project_requirement_unified_semantic_ownership_shadow import build_semantic_ownership_shadow, evidence_ids_from_domain_row

EVIDENCE_ID = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"


def _req(req_id, title, legacy_source_id=None):
    return {"id": req_id, "title": title, "description": "", "requirement_type": "deliverable", "legacy_source_id": legacy_source_id, "truth_state": "verified"}


def _match(req_id, text, locator="page 88", score=0.47, evidence_id=EVIDENCE_ID):
    return {"requirement_id": req_id, "score": score, "evidence": {"evidence_id": evidence_id, "source_name": "proposal.pdf", "locator_text": locator, "text": text}}


def _compat(pairs=()):
    identities = tuple(SimpleNamespace(domain_requirement_id=d, legacy_aliases=(l,)) for l, d in pairs)
    return SimpleNamespace(links=(), identities=identities, pass_data_bridge=True)


def test_evidence_ids_only_reads_evidence_shaped_keys():
    row = {"id": EVIDENCE_ID, "source_evidence_id": EVIDENCE_ID, "attributes": {"evidence_unit_ids": [EVIDENCE_ID], "source_asset_id": "11111111-2222-4333-8444-555555555555"}}
    assert evidence_ids_from_domain_row(row) == {EVIDENCE_ID}


def test_brief_recap_is_excluded_without_ownership_review():
    result = build_semantic_ownership_shadow(
        project_id="p1", legacy_requirement_rows=[_req("l1", "Instagram")], domain_requirement_rows=[],
        legacy_unified={"briefing_matches": [_match("l1", "BRIEF RECAP | OUR GOAL social-first Instagram", locator="page 3")]},
        domain_unified={"briefing_matches": []}, compatibility=_compat(), domain_rows_by_key={},
    )
    assert result.excluded_non_response_legacy_count == 1
    assert result.unresolved_ownership_count == 0
    assert result.status == "PASS_PROJECTED_SEMANTIC_OWNERSHIP"


def test_same_evidence_cross_domain_owner_resolves_residual():
    result = build_semantic_ownership_shadow(
        project_id="p1", legacy_requirement_rows=[_req("l1", "Reels;")], domain_requirement_rows=[],
        legacy_unified={"briefing_matches": [_match("l1", "INSTAGRAM activation with Feed, Stories, Reels and Super Zoom")]},
        domain_unified={"briefing_matches": []}, compatibility=_compat(),
        domain_rows_by_key={"solutions": [{"id": "s1", "title": "Instagram activation", "source_evidence_id": EVIDENCE_ID}]},
    )
    assert result.cross_domain_owned_same_evidence_count == 1
    assert result.unresolved_ownership_count == 0
    row = next(r for r in result.detail_rows if r["side"] == "legacy")
    assert row["contract_disposition"] == "cross_domain_owned_same_evidence"


def test_explicit_material_component_without_owner_requires_review():
    result = build_semantic_ownership_shadow(
        project_id="p1", legacy_requirement_rows=[_req("l1", "Reels;")], domain_requirement_rows=[],
        legacy_unified={"briefing_matches": [_match("l1", "INSTAGRAM activation with Feed, Stories, Reels and Super Zoom")]},
        domain_unified={"briefing_matches": []}, compatibility=_compat(), domain_rows_by_key={},
    )
    assert result.material_response_component_unowned_count == 1
    assert result.status == "PASS_WITH_OWNERSHIP_REVIEW"


def test_governed_mapping_blocks_if_domain_response_is_excluded():
    result = build_semantic_ownership_shadow(
        project_id="p1", legacy_requirement_rows=[_req("l1", "Camera capability")], domain_requirement_rows=[_req("d1", "Camera capability", "l1")],
        legacy_unified={"briefing_matches": [_match("l1", "EVENT PRODUCT REVEAL showcasing camera capability", locator="page 62")]},
        domain_unified={"briefing_matches": [_match("d1", "NATIONAL LAUNCH JOVI X300", locator="page 1", score=0.4, evidence_id="bbbbbbbb-cccc-4ddd-8eee-ffffffffffff")]},
        compatibility=_compat([("l1", "d1")]), domain_rows_by_key={},
    )
    assert result.mapped_response_asymmetry_count == 1
    assert result.status == "BLOCKED_MAPPED_RESPONSE_ASYMMETRY"
