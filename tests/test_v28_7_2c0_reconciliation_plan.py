from project_requirement_reconciliation import build_requirement_reconciliation_plan


PROJECT_ID = "00000000-0000-0000-3000-000000000001"
REQ_ID = "00000000-0000-0000-1000-000000000001"
ENTITY_ID = "00000000-0000-0000-2000-000000000001"
LEGACY_ID = "00000000-0000-0000-4000-000000000001"


def _obs(idx, name, semantic_role, *, confidence=0.98, authority=0.94, requirement_id=REQ_ID, legacy_id=LEGACY_ID):
    return {
        "id": f"00000000-0000-0000-5000-{idx:012d}",
        "source_asset_id": f"00000000-0000-0000-6000-{idx:012d}",
        "evidence_unit_id": f"00000000-0000-0000-7000-{idx:012d}",
        "observed_name": name,
        "observed_type": "deliverable",
        "occurrence_phase": "briefing",
        "semantic_role": semantic_role,
        "model_confidence": confidence,
        "source_authority_score": authority,
        "attributes": {
            "requirement_id": requirement_id,
            "legacy_requirement_id": legacy_id,
            "evidence_text": f"Evidence for {name}",
        },
    }


def _existing():
    return [{
        "id": REQ_ID,
        "entity_id": ENTITY_ID,
        "legacy_source_id": LEGACY_ID,
        "title": "Criar ativação social",
        "description": "Criar uma ativação social específica.",
        "requirement_type": "deliverable",
    }]


def test_existing_requirement_gets_occurrence_and_evidence_not_duplicate_identity():
    plan = build_requirement_reconciliation_plan(PROJECT_ID, [_obs(1, "Criar ativação social", "requirement_candidate")], _existing())
    assert plan["requirements"] == []
    assert len(plan["occurrences"]) == 1
    assert plan["occurrences"][0]["requirement_id"] == REQ_ID
    assert len(plan["evidence_links"]) == 1
    resolution = plan["observation_resolutions"][0]
    assert resolution["status"] == "reconciled"
    assert resolution["resolution_action"] == "attach_requirement_occurrence"


def test_scope_attribute_and_context_do_not_create_requirement_or_occurrence():
    observations = [
        _obs(1, "Canal social", "channel_scope"),
        _obs(2, "Recurso do produto", "product_attribute"),
        _obs(3, "Perfil de público", "audience_context"),
    ]
    plan = build_requirement_reconciliation_plan(PROJECT_ID, observations, _existing())
    assert plan["requirements"] == []
    assert plan["occurrences"] == []
    actions = {row["resolution_action"] for row in plan["observation_resolutions"]}
    assert actions == {"attach_scope", "attach_attribute", "no_domain_object"}


def test_constraint_signal_attaches_as_constraint_occurrence_without_inventing_operator():
    obs = _obs(1, "Respeitar verba", "constraint_candidate")
    plan = build_requirement_reconciliation_plan(PROJECT_ID, [obs], _existing())
    assert len(plan["occurrences"]) == 1
    assert plan["occurrences"][0]["occurrence_role"] == "constraint"
    assert "constraint_operator" not in plan["occurrences"][0]


def test_new_requirement_requires_high_confidence_and_authority():
    obs = _obs(1, "Garantir acessibilidade física", "requirement_candidate", requirement_id=None, legacy_id=None)
    plan = build_requirement_reconciliation_plan(PROJECT_ID, [obs], [])
    assert len(plan["requirements"]) == 1
    assert len(plan["occurrences"]) == 1
    assert plan["observation_resolutions"][0]["resolution_action"] == "create_requirement"

    weak = _obs(2, "Garantir acessibilidade física", "requirement_candidate", confidence=0.80, requirement_id=None, legacy_id=None)
    weak_plan = build_requirement_reconciliation_plan(PROJECT_ID, [weak], [])
    assert weak_plan["requirements"] == []
    assert weak_plan["occurrences"] == []
    assert weak_plan["observation_resolutions"][0]["resolution_action"] == "insufficient_evidence"


def test_plan_never_emits_existing_existing_merge():
    existing = _existing() + [{
        "id": "00000000-0000-0000-1000-000000000002",
        "entity_id": "00000000-0000-0000-2000-000000000002",
        "legacy_source_id": "00000000-0000-0000-4000-000000000002",
        "title": "Criar conteúdo social",
        "description": "Criar conteúdo digital social.",
        "requirement_type": "deliverable",
    }]
    obs = _obs(1, "Criar conteúdo para social", "requirement_candidate", requirement_id=None, legacy_id=None)
    plan = build_requirement_reconciliation_plan(PROJECT_ID, [obs], existing)
    serialized = str(plan).casefold()
    assert '"merge"' not in serialized
    assert "auto_merge" not in serialized
