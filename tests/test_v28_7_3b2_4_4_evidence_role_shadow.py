from __future__ import annotations

from types import SimpleNamespace

from project_requirement_unified_evidence_role_shadow import (
    classify_response_evidence_role,
    build_evidence_role_shadow,
)


def _req(req_id, title, req_type="deliverable", legacy_source_id=None):
    return {
        "id": req_id,
        "title": title,
        "description": "",
        "requirement_type": req_type,
        "legacy_source_id": legacy_source_id,
        "truth_state": "verified",
    }


def _match(req_id, text, locator="page 3", score=0.47):
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


def test_cover_page_is_projected_out():
    role, _, _ = classify_response_evidence_role(
        _req("l1", "Público-alvo", "audience"),
        _match(
            "l1",
            "NATIONAL LAUNCH JOVI X300 ULTRA",
            locator="page 1",
            score=0.53,
        ),
    )
    assert role == "exclude_non_response"


def test_brief_recap_is_projected_out():
    role, _, _ = classify_response_evidence_role(
        _req("l1", "Instagram"),
        _match(
            "l1",
            "BRIEF RECAP | OUR GOAL social-first activations across Instagram",
            locator="page 3",
        ),
    )
    assert role == "exclude_non_response"


def test_real_activation_page_is_retained():
    role, _, _ = classify_response_evidence_role(
        _req("l1", "Reels;"),
        _match(
            "l1",
            "INSTAGRAM — SUPER ZOOM SUPER LIKES. A platform with feed, Stories, Reels. For this activation...",
            locator="page 88",
        ),
    )
    assert role == "retain_response_candidate"


def test_projected_shadow_can_narrow_to_residual_semantic_review():
    legacy_rows = [
        _req("l1", "Instagram"),
        _req("l2", "Reels;"),
    ]
    domain_rows = []
    legacy_unified = {
        "briefing_matches": [
            _match(
                "l1",
                "BRIEF RECAP | OUR GOAL social-first activations across Instagram",
            ),
            _match(
                "l2",
                "INSTAGRAM — SUPER ZOOM SUPER LIKES. A platform with feed, Stories, Reels. For this activation...",
                locator="page 88",
            ),
        ]
    }
    result = build_evidence_role_shadow(
        project_id="p1",
        legacy_requirement_rows=legacy_rows,
        domain_requirement_rows=domain_rows,
        legacy_link_rows=[],
        legacy_unified=legacy_unified,
        domain_unified={"briefing_matches": []},
        compatibility=_compat_no_alias(),
    )
    assert result.raw_legacy_match_count == 2
    assert result.projected_legacy_match_count == 1
    assert result.excluded_legacy_count == 1
    assert result.status == "PROJECTED_RESIDUAL_SEMANTIC_REVIEW"
