from __future__ import annotations

from types import SimpleNamespace
from project_requirement_unified_semantic_audit import (
    audit_unified_semantic_counterparts,
    _evidence_quality_signals,
)


def _legacy(req_id, title, req_type="deliverable"):
    return {"id": req_id, "title": title, "description": "", "requirement_type": req_type}


def _domain(req_id, title, req_type="deliverable", legacy_source_id=None):
    return {
        "id": req_id,
        "title": title,
        "description": "",
        "requirement_type": req_type,
        "truth_state": "verified",
        "legacy_source_id": legacy_source_id,
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


def _compat():
    # no structural aliases for pure divergent-set tests
    return SimpleNamespace(identities=(), links=(), pass_data_bridge=True)


def test_cover_page_is_high_review_risk():
    status, flags = _evidence_quality_signals(
        _legacy("l1", "Público-alvo", "audience"),
        _match("l1", "NATIONAL LAUNCH JOVI X300 ULTRA", locator="page 1", score=0.53),
    )
    assert status == "HIGH_REVIEW_RISK"
    assert "COVER_OR_TITLE_PAGE_RISK" in flags


def test_brief_recap_platform_is_restatement_risk():
    status, flags = _evidence_quality_signals(
        _legacy("l1", "Instagram"),
        _match("l1", "BRIEF RECAP | OUR GOAL social-first activations across Instagram", locator="page 3"),
    )
    assert status == "REVIEW_RESTATEMENT_RISK"
    assert "PLATFORM_MENTION_IN_RECAP_RISK" in flags


def test_stories_without_instagram_context_is_high_review_risk():
    status, flags = _evidence_quality_signals(
        _legacy("l1", "Stories."),
        _match("l1", "Every lens tells a different story about Brazil", locator="page 66"),
    )
    assert status == "HIGH_REVIEW_RISK"
    assert "AMBIGUOUS_STORIES_TERM_RISK" in flags


def test_semantic_candidate_rows_are_diagnostic_only():
    legacy_rows = [_legacy("l1", "Instagram")]
    domain_rows = [_domain("d1", "Ativação Instagram: Aesthetics & Lifestyle Gallery")]
    result = audit_unified_semantic_counterparts(
        project_id="p1",
        legacy_requirement_rows=legacy_rows,
        domain_requirement_rows=domain_rows,
        legacy_unified={"briefing_matches": [_match("l1", "BRIEF RECAP | OUR GOAL Instagram", score=0.47)]},
        domain_unified={"briefing_matches": []},
        compatibility=_compat(),
    )
    assert result.legacy_divergent_match_count == 1
    assert result.detail_rows
    assert result.detail_rows[0]["candidate_requirement_id"] == "d1"
    assert result.detail_rows[0]["candidate_rank"] == 1
