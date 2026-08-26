from __future__ import annotations

from project_requirement_relational_shadow import _normalise_domain_requirement
from project_requirement_unified_input_audit import _production_briefing_pair_score


def test_domain_shadow_title_uses_b1_adapter_precedence():
    row = {
        "id": "d1",
        "truth_state": "verified",
        "requirement_name": "Público-alvo",
        "title": "Público-Alvo: Young White Collars (26 a 35 anos)",
        "description": "Descrição extensa",
        "requirement_type": "audience",
        "mandatory": False,
        "priority": "high",
    }
    normalised = _normalise_domain_requirement(row)
    assert normalised is not None
    assert normalised["title"] == "Público-alvo"
    assert normalised["_domain_adapter_parity"] == "V28.7.3B2.4.2"


def test_domain_shadow_source_quote_uses_b1_source_excerpt_precedence():
    row = {
        "id": "d1",
        "truth_state": "verified",
        "requirement_name": "Instagram",
        "description": "Ativação Instagram",
        "observed_text": "Trecho observado",
        "source_quote": "Trecho secundário",
        "requirement_type": "deliverable",
    }
    normalised = _normalise_domain_requirement(row)
    assert normalised is not None
    assert normalised["source_quote"] == "Trecho observado"


def test_production_pair_score_includes_overlap_floor():
    score = _production_briefing_pair_score(
        "Objetivo principal lançamento premium câmera design posicionamento mercado brasil experiência consumidores",
        "Showcase camera design and premium positioning for consumers in Brazil",
    )
    assert 0.0 < score <= 0.98


def test_production_pair_score_exact_platform_name_is_nonzero():
    score = _production_briefing_pair_score(
        "Instagram deliverable",
        "INSTAGRAM — SUPER ZOOM SUPER LIKES",
    )
    assert score > 0.0
