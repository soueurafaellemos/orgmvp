from __future__ import annotations

from cross_source_linker import cost_link_score
from entity_resolution import ResolutionEntity


def _source(entity_id: str, name: str, entity_type: str = "activation") -> ResolutionEntity:
    return ResolutionEntity(
        id=entity_id,
        entity_type=entity_type,
        canonical_name=name,
        scope_entity_id="project-1",
        confidence=0.9,
    )


def _line(entity_id: str, name: str, *, description: str = "", category: str = "7. ATIVAÇÃO") -> ResolutionEntity:
    return ResolutionEntity(
        id=entity_id,
        entity_type="financial_line_item",
        canonical_name=name,
        scope_entity_id="project-1",
        confidence=0.95,
        attributes={"description": description, "category": category},
    )


def test_exact_named_activations_can_be_auto_linked_to_cost_lines():
    for name in ("Origami coração", "Amarelinha", "Pescaria"):
        score, reasons = cost_link_score(_source("s", name), _line("l", name))
        assert score >= 0.86, (name, score, reasons)


def test_partial_gift_name_does_not_silently_auto_link():
    score, _ = cost_link_score(
        _source("s", "Meia Coraçãozinho", entity_type="gift"),
        _line("l", "Meia", category="5. BRINDES"),
    )
    assert score < 0.74


def test_ineligible_types_do_not_create_cost_links():
    source = _source("s", "Nostalgia", entity_type="concept")
    score, reasons = cost_link_score(source, _line("l", "Nostalgia"))
    assert score == 0
    assert reasons
