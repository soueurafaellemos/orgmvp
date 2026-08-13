from entity_resolution import ResolutionEntity, entity_match_score
from cross_source_linker import cost_link_score
from project_entity_graph import _canonical_title, _is_useful_name, _item_type


def _e(eid, etype, name, *, kind="project_instance"):
    return ResolutionEntity(
        id=eid,
        entity_type=etype,
        canonical_name=name,
        scope_entity_id="project-1",
        entity_kind=kind,
        confidence=0.95,
    )


def test_activation_and_solution_with_same_distinctive_name_can_unify():
    left = _e("a", "activation", "Amarelinha", kind="canonical")
    right = _e("b", "solution", "Amarelinha")
    match = entity_match_score(left, right)
    assert match.decision == "AUTO_MERGE"
    assert match.score >= 0.91


def test_activation_and_gift_do_not_merge_only_because_name_matches():
    left = _e("a", "activation", "Press Kit")
    right = _e("b", "gift", "Press Kit")
    match = entity_match_score(left, right)
    assert match.decision == "DISTINCT"


def test_generic_presskit_name_is_not_forced_across_types():
    left = _e("a", "presskit", "Press Kit", kind="canonical")
    right = _e("b", "gift", "Press Kit")
    match = entity_match_score(left, right)
    assert match.decision != "AUTO_MERGE"


def test_workspace_titles_become_short_canonical_names():
    assert _canonical_title({"title": "apresenta BRINCADEIRAS AMARELINHA"}) == "AMARELINHA"
    assert _is_useful_name("AMARELINHA")
    assert not _is_useful_name("BRINCADEIRAS")


def test_workspace_section_drives_canonical_type():
    assert _item_type({"section_key": "activations", "title": "Pescaria"}) == "activation"
    assert _item_type({"section_key": "gifts", "title": "Press kit"}) == "presskit"
    assert _item_type({"section_key": "scenography", "title": "Casa Chambinho"}) == "solution"


def test_zero_value_named_activation_still_links_to_its_cost_line():
    source = _e("s", "activation", "Pescaria", kind="canonical")
    target = ResolutionEntity(
        id="c",
        entity_type="financial_line_item",
        canonical_name="Ativação - Pescaria",
        scope_entity_id="project-1",
        confidence=0.98,
        attributes={"category": "7. ATIVAÇÃO", "description": "Ativação - Pescaria", "client_total": 0},
    )
    score, _ = cost_link_score(source, target)
    assert score >= 0.86
