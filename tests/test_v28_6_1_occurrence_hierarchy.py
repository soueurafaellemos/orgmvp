from cross_source_linker import canonical_occurrence_score, cost_link_score, presskit_component_score
from entity_resolution import ResolutionEntity
from project_entity_graph import _alias_variants


def _entity(eid, etype, name, *, kind="project_instance", aliases=()):
    return ResolutionEntity(
        id=eid,
        entity_type=etype,
        canonical_name=name,
        aliases=tuple(aliases),
        entity_kind=kind,
        scope_entity_id="project-1",
        confidence=0.95,
    )


def test_workspace_alias_variants_remove_structural_prefix_only():
    assert "Origami de Coração" in _alias_variants("Oficina Origami de Coração")
    assert "Pescaria" in _alias_variants("Ativação - Pescaria")


def test_occurrence_link_uses_evidence_when_extracted_name_is_generic():
    canonical = _entity("c", "activation", "Amarelinha", kind="canonical")
    candidate = _entity("o", "solution", "Atividade de recreação")
    score, reasons = canonical_occurrence_score(
        canonical,
        candidate,
        candidate_text="AMARELINHA Brincadeira tradicional executada no evento para crianças e famílias.",
        candidate_roles=("post_event_report",),
    )
    assert score >= 0.92
    assert any("evidência" in reason for reason in reasons)


def test_occurrence_link_does_not_use_year_as_identity():
    canonical = _entity("c", "activation", "Pescaria", kind="canonical")
    candidate = _entity("o", "solution", "2026")
    score, _ = canonical_occurrence_score(
        canonical,
        candidate,
        candidate_text="Festivalzinho 2026 realizado no Parque Villa Lobos.",
        candidate_roles=("post_event_report",),
    )
    assert score < 0.74


def test_presskit_component_requires_presskit_context_and_item_mention():
    assert presskit_component_score(
        "Meias",
        "PRESS KIT para influenciadores: meia personalizada com coração e cadarço personalizado.",
    ) >= 0.90
    assert presskit_component_score("Meias", "Brindes gerais: adesivos e tatuagens.") == 0.0


def test_cost_link_handles_structural_prefixes_for_activation():
    source = _entity("s", "activation", "Oficina Origami de Coração", kind="canonical", aliases=("Origami de Coração", "Origami"))
    line = ResolutionEntity(
        id="l",
        entity_type="financial_line_item",
        canonical_name="Ativação - Oficina de Origami",
        scope_entity_id="project-1",
        confidence=0.98,
        attributes={"category": "ATIVAÇÃO", "description": "Ativação - Oficina de Origami", "client_total": 14000},
    )
    score, _ = cost_link_score(source, line)
    assert score >= 0.86
