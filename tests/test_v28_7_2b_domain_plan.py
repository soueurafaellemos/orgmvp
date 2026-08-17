from project_core_semantic_domains import build_core_semantic_plan


def obs(i, domain, role, name, evidence, *, asset="a", assertion="source_explicit", confidence=.98, attrs=None):
    return {
        "id": i,
        "source_asset_id": asset,
        "evidence_unit_id": evidence,
        "domain_hint": domain,
        "semantic_role": role,
        "observed_name": name,
        "assertion_mode": assertion,
        "model_confidence": confidence,
        "source_authority_score": .88,
        "attributes": attrs or {"statement": name},
    }


def test_identity_is_not_evidence_occurrence_for_strategy_and_creative():
    plan = build_core_semantic_plan("p", [
        obs("s1", "strategy", "territory", "Nostalgia", "e1"),
        obs("s2", "strategy", "territory", "Nostalgia", "e2"),
        obs("c1", "creative", "pov", "The Big House", "e3"),
        obs("c2", "creative", "pov", "The Big House", "e4"),
    ])
    assert len(plan["strategy_elements"]) == 1
    assert set(plan["strategy_elements"][0]["evidence_ids"]) == {"e1", "e2"}
    assert len(plan["creative_platforms"]) == 1
    assert len(plan["creative_elements"]) == 1
    assert set(plan["creative_platforms"][0]["evidence_ids"]) == {"e3", "e4"}


def test_analyst_inference_never_materializes_domain_truth():
    plan = build_core_semantic_plan("p", [
        obs("s", "strategy", "insight", "A nice interpretation", "e1", assertion="analyst_inference"),
    ])
    assert plan["strategy_elements"] == []
    assert plan["creative_platforms"] == []


def test_journey_is_not_created_without_explicit_architecture():
    plan = build_core_semantic_plan("p", [
        obs("j", "journey", "moment", "PRODUCT REVEAL", "e2", attrs={"moment_type": "product_reveal"}),
    ])
    assert plan["journey_moments"] == []
    resolution = plan["observation_resolutions"][0]
    assert resolution["status"] == "open"
    assert resolution["resolution_action"] == "insufficient_evidence"


def test_unique_explicit_architecture_can_organize_separate_explicit_moment_as_synthesis_link():
    plan = build_core_semantic_plan("p", [
        obs("e", "experience", "experience_architecture", "EVENT JOURNEY", "e1"),
        obs("j", "journey", "moment", "PRODUCT REVEAL", "e2", attrs={"moment_type": "product_reveal", "parent_stage_hint": "event"}),
    ])
    assert len(plan["experience_architectures"]) == 1
    assert len(plan["journey_moments"]) == 1
    assert plan["journey_moments"][0]["assertion_mode"] == "source_explicit"
    assert plan["journey_moments"][0]["architecture_association_mode"] == "evidence_synthesis"


def test_multiple_creative_platforms_are_not_collapsed():
    plan = build_core_semantic_plan("p", [
        obs("c1", "creative", "big_idea", "Route One", "e1"),
        obs("c2", "creative", "big_idea", "Route Two", "e2"),
    ])
    assert {row["name"] for row in plan["creative_platforms"]} == {"Route One", "Route Two"}


def test_creative_element_does_not_become_parallel_platform_without_platform_signal():
    plan = build_core_semantic_plan("p", [
        obs("m", "creative", "message", "A message", "e1"),
    ])
    assert plan["creative_platforms"] == []
    assert plan["creative_elements"] == []
    resolution = plan["observation_resolutions"][0]
    assert resolution["status"] == "open"
    assert resolution["resolution_action"] == "insufficient_evidence"


def test_unique_same_source_platform_can_organize_separate_explicit_creative_element_as_inference_link():
    plan = build_core_semantic_plan("p", [
        obs("p1", "creative", "big_idea", "Route One", "e1", asset="a"),
        obs("m1", "creative", "message", "Create through your own lens", "e2", asset="a"),
    ])
    assert len(plan["creative_platforms"]) == 1
    assert len(plan["creative_elements"]) == 2
    message = next(row for row in plan["creative_elements"] if row["creative_type"] == "message")
    assert message["platform_association_mode"] == "evidence_synthesis"
