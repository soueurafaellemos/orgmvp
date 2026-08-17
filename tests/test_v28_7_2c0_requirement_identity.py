from project_requirement_identity import resolve_requirement_identity


EXISTING = [
    {
        "id": "00000000-0000-0000-1000-000000000001",
        "entity_id": "00000000-0000-0000-2000-000000000001",
        "legacy_source_id": "00000000-0000-0000-3000-000000000001",
        "title": "Criar ativação específica para plataforma social",
        "description": "A ativação deve demonstrar o produto em uma plataforma social.",
        "requirement_type": "deliverable",
    },
    {
        "id": "00000000-0000-0000-1000-000000000002",
        "entity_id": "00000000-0000-0000-2000-000000000002",
        "legacy_source_id": "00000000-0000-0000-3000-000000000002",
        "title": "Respeitar verba informada",
        "description": "O projeto deve respeitar o orçamento indicado no briefing.",
        "requirement_type": "budget",
    },
]


def test_explicit_requirement_lineage_wins_over_text_similarity():
    obs = {
        "observed_name": "Plataforma",
        "observed_type": "deliverable",
        "attributes": {"requirement_id": EXISTING[0]["id"]},
    }
    resolved = resolve_requirement_identity(obs, EXISTING)
    assert resolved["action"] == "attach_existing"
    assert resolved["target"]["id"] == EXISTING[0]["id"]
    assert resolved["reason"] == "explicit_requirement_id"


def test_legacy_lineage_attaches_same_identity_without_merge():
    obs = {
        "observed_name": "Outro texto da mesma obrigação",
        "observed_type": "deliverable",
        "attributes": {"legacy_requirement_id": EXISTING[0]["legacy_source_id"]},
    }
    resolved = resolve_requirement_identity(obs, EXISTING)
    assert resolved["action"] == "attach_existing"
    assert resolved["target"]["id"] == EXISTING[0]["id"]


def test_two_plausible_existing_requirements_are_reviewed_not_merged():
    existing = [
        {"id": "a", "title": "Criar conteúdo social para lançamento", "description": "Conteúdo social de lançamento", "requirement_type": "deliverable"},
        {"id": "b", "title": "Criar conteúdo digital para lançamento", "description": "Conteúdo digital de lançamento", "requirement_type": "deliverable"},
    ]
    resolved = resolve_requirement_identity(
        {"observed_name": "Criar conteúdo para lançamento", "observed_type": "deliverable", "attributes": {}},
        existing,
    )
    assert resolved["action"] == "review_required"
    assert "merge" not in str(resolved).casefold()


def test_no_plausible_existing_identity_returns_create_candidate_only():
    resolved = resolve_requirement_identity(
        {"observed_name": "Garantir acessibilidade física no espaço", "observed_type": "operation", "attributes": {}},
        EXISTING,
    )
    assert resolved["action"] == "create_new"
