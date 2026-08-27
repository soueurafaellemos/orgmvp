from __future__ import annotations

from types import SimpleNamespace

from project_requirement_cross_domain_residual_audit import (
    audit_cross_domain_residual_placement,
    _object_text,
)


def _req(req_id, title, req_type="deliverable"):
    return {
        "id": req_id,
        "title": title,
        "description": "",
        "requirement_type": req_type,
    }


def _match(req_id, text, locator="page 62", score=0.62):
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
    return SimpleNamespace(
        links=(),
        identities=(),
        pass_data_bridge=True,
    )


def test_object_text_excludes_ids_and_keeps_semantics():
    row = {
        "id": "abc",
        "title": "Camera experience",
        "description": "Hands-on testing of camera capabilities",
        "source_evidence_id": "ev1",
        "attributes": {"platform": "Instagram"},
    }
    text = _object_text(row)
    assert "Camera experience" in text
    assert "Hands-on testing" in text
    assert "Instagram" in text
    assert "ev1" not in text


def test_brief_recap_residual_is_not_audited():
    result = audit_cross_domain_residual_placement(
        project_id="p1",
        legacy_requirement_rows=[_req("l1", "Instagram")],
        legacy_unified={
            "briefing_matches": [
                _match(
                    "l1",
                    "BRIEF RECAP | OUR GOAL Instagram",
                    locator="page 3",
                    score=0.47,
                )
            ]
        },
        compatibility=_compat_no_alias(),
        domain_rows_by_key={"solutions": [{"id": "s1", "title": "Instagram activation"}]},
    )
    assert result.status == "PASS_NO_RETAINED_RESIDUALS"
    assert result.retained_residual_count == 0


def test_material_camera_residual_finds_solution_candidate():
    result = audit_cross_domain_residual_placement(
        project_id="p1",
        legacy_requirement_rows=[
            _req("l1", "A superioridade das câmeras do JOVI X300 Ultra;")
        ],
        legacy_unified={
            "briefing_matches": [
                _match(
                    "l1",
                    "EVENT PRODUCT REVEAL showcasing the cameras capabilities",
                    locator="page 62",
                )
            ]
        },
        compatibility=_compat_no_alias(),
        domain_rows_by_key={
            "solutions": [{
                "id": "s1",
                "title": "JOVI X300 Ultra Camera Product Reveal",
                "description": "Reveal demonstrating camera capabilities",
            }],
            "strategy": [{
                "id": "st1",
                "title": "Premium launch positioning",
            }],
        },
    )
    assert result.retained_residual_count == 1
    assert result.detail_rows
    top_solution = next(
        row for row in result.detail_rows
        if row["candidate_domain_key"] == "solutions"
        and row["candidate_rank_within_domain"] == 1
    )
    assert top_solution["candidate_object_id"] == "s1"
    assert top_solution["candidate_rank_score"] > 0.0


def test_reels_can_rank_creative_candidate():
    result = audit_cross_domain_residual_placement(
        project_id="p1",
        legacy_requirement_rows=[_req("l1", "Reels;")],
        legacy_unified={
            "briefing_matches": [
                _match(
                    "l1",
                    "INSTAGRAM activation with Feed Stories Reels and Super Zoom",
                    locator="page 88",
                    score=0.47,
                )
            ]
        },
        compatibility=_compat_no_alias(),
        domain_rows_by_key={
            "creative": [{
                "id": "c1",
                "_domain_object_type": "creative_element",
                "title": "Instagram Reels content mechanic",
                "description": "Super Zoom social content",
            }],
        },
    )
    assert result.retained_residual_count == 1
    top = result.detail_rows[0]
    assert top["candidate_domain_key"] == "creative"
    assert top["candidate_rank_score"] > 0.0
