from __future__ import annotations

import cross_source_linker as csl
from project_entity_graph import _is_useful_name


def _snapshot(*, briefing_score: float = 0.86):
    return {
        "project_entity_id": "project-entity",
        "entities": [
            {"id": "c1", "entity_kind": "canonical", "entity_type": "activation", "canonical_name": "Amarelinha", "attributes": {"semantic_family": "project_solution"}},
            {"id": "p1", "entity_kind": "project_instance", "entity_type": "activation", "canonical_name": "Amarelinha", "canonical_entity_id": "c1", "domain_table": "memory_items", "domain_id": "m1", "attributes": {"occurrence_role": "proposal"}},
            {"id": "x1", "entity_kind": "project_instance", "entity_type": "activation", "canonical_name": "Amarelinha", "canonical_entity_id": "c1", "domain_table": "memory_item_outcomes", "domain_id": "o1", "attributes": {"occurrence_role": "execution"}},
            {"id": "f1", "entity_kind": "project_instance", "entity_type": "financial_line_item", "canonical_name": "Ativação - Amarelinha", "domain_table": "memory_cost_items", "domain_id": "cost1", "attributes": {}},
            {"id": "r1", "entity_kind": "project_instance", "entity_type": "requirement", "canonical_name": "Espaço e ativações", "domain_table": "memory_briefing_requirements", "domain_id": "req1", "attributes": {}},
        ],
        "workspace_cost_links": [{"id": "cl1", "memory_item_id": "m1", "cost_item_id": "cost1", "match_score": 0.94, "link_status": "suggested", "match_reason": "nome e categoria"}],
        "workspace_briefing_links": [{"id": "bl1", "memory_item_id": "m1", "requirement_id": "req1", "match_score": briefing_score, "link_status": "suggested", "match_reason": "demanda x ficha"}],
        "workspace_outcomes": [{"id": "o1", "item_id": "m1", "outcome_status": "executed", "information_source": "document", "confidence_level": "inferred"}],
        "roles_by_entity": {},
    }


def test_presskit_is_allowed_as_container_entity_not_generic_heading():
    assert _is_useful_name("Press Kit", entity_type="presskit")
    assert not _is_useful_name("Press Kit")


def test_structured_workspace_links_are_projected_into_graph(monkeypatch):
    relations = []
    claims = []

    def fake_relation(_client, **kwargs):
        relations.append(kwargs)
        return True

    def fake_claim(_client, **kwargs):
        claims.append(kwargs)
        return True

    monkeypatch.setattr(csl, "_persist_relation", fake_relation)
    monkeypatch.setattr(csl, "_persist_text_claim", fake_claim)

    result = csl._structured_workspace_relations(object(), _snapshot(), "run-1")

    assert result["cost_links"] == 1
    assert result["briefing_links"] == 1
    assert result["execution_claims"] == 1
    assert any(r["relation_type"] == "costed_by" and r["source_id"] == "c1" and r["target_id"] == "f1" for r in relations)
    assert any(r["relation_type"] == "responds_to" and r["source_id"] == "c1" and r["target_id"] == "r1" for r in relations)
    assert any(c["predicate"] == "execution_result" and c["subject_id"] == "c1" and c["value_text"] == "executed" for c in claims)


def test_noisy_briefing_suggestion_stays_review_instead_of_becoming_truth(monkeypatch):
    relations = []

    def fake_relation(_client, **kwargs):
        relations.append(kwargs)
        return True

    monkeypatch.setattr(csl, "_persist_relation", fake_relation)
    monkeypatch.setattr(csl, "_persist_text_claim", lambda *_a, **_k: True)

    result = csl._structured_workspace_relations(object(), _snapshot(briefing_score=0.66), "run-1")

    assert result["briefing_links"] == 0
    assert any(review["kind"] == "briefing" for review in result["reviews"])
    assert not any(r["relation_type"] == "responds_to" for r in relations)
