from __future__ import annotations

from types import SimpleNamespace

from project_requirement_unified_residual_coverage import (
    audit_residual_evidence_coverage,
    _candidate_class,
)


def _req(req_id, title, req_type="deliverable", legacy_source_id=None):
    return {
        "id": req_id,
        "title": title,
        "description": "",
        "source_quote": "",
        "requirement_type": req_type,
        "legacy_source_id": legacy_source_id,
        "truth_state": "verified",
    }


def _match(req_id, text, locator="page 62", score=0.47):
    return {
        "requirement_id": req_id,
        "score": score,
        "evidence": {
            "evidence_id": f"ev-{req_id}",
            "source_name": "proposal.pdf",
            "locator_text": locator,
            "text": text,
        },
    }


def _compat_no_alias():
    return SimpleNamespace(links=(), identities=(), pass_data_bridge=True)


def test_candidate_class_full_support():
    assert _candidate_class(full_score=0.42, title_score=0.30) == \
        "DOMAIN_FULL_INPUT_SUPPORTS_SAME_EVIDENCE"


def test_candidate_class_title_only_support():
    assert _candidate_class(full_score=0.20, title_score=0.47) == \
        "TITLE_ONLY_SUPPORTS_SAME_EVIDENCE"


def test_no_retained_residuals_passes():
    legacy = [_req("l1", "Instagram")]
    result = audit_residual_evidence_coverage(
        project_id="p1",
        legacy_requirement_rows=legacy,
        domain_requirement_rows=[],
        legacy_unified={
            "briefing_matches": [
                _match(
                    "l1",
                    "BRIEF RECAP | OUR GOAL Instagram",
                    locator="page 3",
                )
            ]
        },
        domain_unified={"briefing_matches": []},
        compatibility=_compat_no_alias(),
    )
    assert result.status == "PASS_NO_RETAINED_RESIDUALS"
    assert result.retained_legacy_residual_count == 0


def test_material_residual_is_ranked_against_domain_requirements():
    legacy = [_req("l1", "A superioridade das câmeras do JOVI X300 Ultra;")]
    domain = [
        _req(
            "d1",
            "Experience & Hands-On Lab: JOVI X300 Ultra",
            "other",
        ),
        _req("d2", "Pesquisa de satisfação"),
    ]
    evidence = (
        "EVENT PRODUCT REVEAL. The brand representative will introduce the "
        "JOVI X300 Ultra, showcasing the cameras capabilities."
    )
    result = audit_residual_evidence_coverage(
        project_id="p1",
        legacy_requirement_rows=legacy,
        domain_requirement_rows=domain,
        legacy_unified={"briefing_matches": [_match("l1", evidence, score=0.62)]},
        domain_unified={"briefing_matches": []},
        compatibility=_compat_no_alias(),
    )
    assert result.retained_legacy_residual_count == 1
    assert result.detail_rows
    assert result.detail_rows[0]["candidate_rank"] == 1
    assert result.detail_rows[0]["domain_requirement_id"] == "d1"
