from project_semantic_relations import plan_core_semantic_relations


def test_shared_evidence_creates_fact_relations_but_same_source_cross_page_is_inference():
    strategy = [{"id":"s","entity_id":"se","source_evidence_id":"e1","evidence_ids":["e1"],"attributes":{"source_asset_ids":["a"]}}]
    creative = [{"id":"c","entity_id":"ce","source_evidence_id":"e2","evidence_ids":["e2"],"attributes":{"source_asset_ids":["a"]}}]
    elements = [{"id":"el","entity_id":"ele","platform_id":"c","source_evidence_id":"e2","evidence_ids":["e2"],"attributes":{"source_asset_ids":["a"]}}]
    rels = plan_core_semantic_relations(
        "p", strategy_elements=strategy, creative_platforms=creative, creative_elements=elements,
        experience_architectures=[], journey_moments=[]
    )
    expressed = [r for r in rels if r["relation_type"] == "expressed_by"]
    assert len(expressed) == 1
    assert expressed[0]["relation_kind"] == "inference"
    contains = [r for r in rels if r["relation_type"] == "contains" and r["target_entity_id"] == "ele"]
    assert len(contains) == 1 and contains[0]["relation_kind"] == "fact"


def test_multiple_creative_routes_do_not_get_strategy_inference_by_project_proximity():
    strategy = [{"id":"s","entity_id":"se","source_evidence_id":"e1","evidence_ids":["e1"],"attributes":{"source_asset_ids":["a"]}}]
    creative = [
        {"id":"c1","entity_id":"c1e","source_evidence_id":"e2","evidence_ids":["e2"],"attributes":{"source_asset_ids":["a"]}},
        {"id":"c2","entity_id":"c2e","source_evidence_id":"e3","evidence_ids":["e3"],"attributes":{"source_asset_ids":["a"]}},
    ]
    rels = plan_core_semantic_relations(
        "p", strategy_elements=strategy, creative_platforms=creative, creative_elements=[],
        experience_architectures=[], journey_moments=[]
    )
    assert not any(r["relation_type"] == "expressed_by" for r in rels)


def test_cross_evidence_architecture_membership_is_explicit_inference_with_both_evidences():
    experience = [{"id":"x","entity_id":"xe","source_evidence_id":"e1","evidence_ids":["e1"],"attributes":{"source_asset_ids":["a"]}}]
    moments = [{"id":"j","entity_id":"je","architecture_id":"x","source_evidence_id":"e2","evidence_ids":["e2"],"architecture_association_mode":"evidence_synthesis","attributes":{"source_asset_ids":["a"]}}]
    rels = plan_core_semantic_relations(
        "p", strategy_elements=[], creative_platforms=[], creative_elements=[],
        experience_architectures=experience, journey_moments=moments
    )
    rel = next(r for r in rels if r["source_entity_id"] == "xe" and r["target_entity_id"] == "je")
    assert rel["relation_kind"] == "inference"
    assert set(rel["evidence_unit_ids"]) == {"e1", "e2"}


def test_cross_evidence_creative_element_membership_is_inference_with_both_evidences():
    creative = [{"id":"c","entity_id":"ce","source_evidence_id":"e1","evidence_ids":["e1"],"attributes":{"source_asset_ids":["a"]}}]
    elements = [{"id":"el","entity_id":"ele","platform_id":"c","source_evidence_id":"e2","evidence_ids":["e2"],"platform_association_mode":"evidence_synthesis","attributes":{"source_asset_ids":["a"],"platform_association_mode":"evidence_synthesis"}}]
    rels = plan_core_semantic_relations(
        "p", strategy_elements=[], creative_platforms=creative, creative_elements=elements,
        experience_architectures=[], journey_moments=[]
    )
    rel = next(r for r in rels if r["source_entity_id"] == "ce" and r["target_entity_id"] == "ele")
    assert rel["relation_kind"] == "inference"
    assert set(rel["evidence_unit_ids"]) == {"e1", "e2"}
