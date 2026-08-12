from __future__ import annotations

import pytest

from entity_resolution import ResolutionEntity, entity_match_score, resolve_entities


def _e(entity_id: str, entity_type: str, name: str, *, scope: str = "project-1", aliases=()):
    return ResolutionEntity(
        id=entity_id,
        entity_type=entity_type,
        canonical_name=name,
        aliases=tuple(aliases),
        scope_entity_id=scope,
        confidence=0.85,
    )


def test_cinemateca_alias_auto_merges_inside_same_project():
    left = _e("a", "venue", "Cinemateca")
    right = _e("b", "venue", "Cinemateca Brasileira")
    match = entity_match_score(left, right)
    assert match.decision == "AUTO_MERGE"
    assert match.score >= 0.91


def test_short_concept_alias_auto_merges_when_phrase_is_preserved():
    left = _e("a", "concept", "ON TOUR")
    right = _e("b", "concept", "JOVI X300 Series ON TOUR")
    match = entity_match_score(left, right)
    assert match.decision == "AUTO_MERGE"
    assert match.score >= 0.91


def test_origami_variants_are_reviewed_not_silently_merged():
    left = _e("a", "activation", "Oficina de Origami")
    right = _e("b", "activation", "Origami coração")
    match = entity_match_score(left, right)
    assert match.decision == "REVIEW"
    assert 0.74 <= match.score < 0.91


def test_different_entity_types_never_merge_even_with_same_name():
    left = _e("a", "gift", "Press Kit")
    right = _e("b", "activation", "Press Kit")
    match = entity_match_score(left, right)
    assert match.decision == "DISTINCT"
    assert match.score == 0


def test_event_journey_and_press_kit_remain_distinct():
    left = _e("a", "deliverable", "EVENT JOURNEY")
    right = _e("b", "deliverable", "PRESS KIT")
    match = entity_match_score(left, right)
    assert match.decision == "DISTINCT"


def test_auto_merge_clusters_choose_one_canonical_and_preserve_alias():
    entities = [
        _e("a", "venue", "Cinemateca"),
        _e("b", "venue", "Cinemateca Brasileira"),
        _e("c", "venue", "Outro Espaço"),
    ]
    clusters, reviews = resolve_entities(entities)
    assert len(clusters) == 1
    assert set(clusters[0].member_ids) == {"a", "b"}
    assert reviews == []
