from project_domain_identity import resolve_observed_identity


EXISTING = [
    {"id": "jogo", "name": "Jogo da memória"},
    {"id": "mascote", "name": "Mascote em Tamanho Real"},
    {"id": "origami", "name": "Oficina Origami de Coração"},
    {"id": "tattoo", "name": "Tatuagens Temporárias"},
    {"id": "pelucia", "name": "Pelúcia"},
    {"id": "chaveiro", "name": "Chaveiro"},
]


def test_exact_and_execution_aliases_attach_to_one_existing_identity():
    assert resolve_observed_identity("Jogo da Memória", EXISTING)["target"]["id"] == "jogo"
    assert resolve_observed_identity("Mascote Chambinho (Chambão)", EXISTING)["target"]["id"] == "mascote"
    assert resolve_observed_identity("Oficina de Origami", EXISTING)["target"]["id"] == "origami"
    assert resolve_observed_identity("Tatuagem", EXISTING)["target"]["id"] == "tattoo"


def test_missing_golden_solutions_are_new_identity_candidates():
    for name in ("Amarelinha", "Pescaria", "Distribuição de Produtos", "Folhas para colorir"):
        resolved = resolve_observed_identity(name, EXISTING)
        assert resolved["action"] == "create_new", (name, resolved)


def test_plausible_existing_identity_is_reviewed_not_duplicated():
    existing = [{"id": "a", "name": "Oficina de Customização"}, {"id": "b", "name": "Oficina de Personalização"}]
    resolved = resolve_observed_identity("Oficina Personalizada", existing)
    assert resolved["action"] == "review_required"


def test_identity_policy_has_no_existing_existing_merge_action():
    for name in ("Pelúcia", "Chaveiro", "Pelúcia de coração"):
        result = resolve_observed_identity(name, EXISTING)
        assert result["action"] in {"attach_existing", "review_required", "create_new"}
        assert result["action"] != "merge"
