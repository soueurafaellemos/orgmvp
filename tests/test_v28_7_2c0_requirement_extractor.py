from project_requirement_semantic_extractor import _best_requirement_evidence, _classify


def test_short_channel_fragment_is_scope_not_requirement_truth():
    kind, role, occurrence_role = _classify(
        {"title": "YouTube", "requirement_type": "channel", "mandatory": False},
        "Criar uma ativação para YouTube com conteúdo social dedicado.",
    )
    assert kind == "scope_signal"
    assert role == "channel_scope"
    assert occurrence_role == "scope"


def test_audience_fragment_is_context_not_requirement_identity():
    kind, role, occurrence_role = _classify(
        {"title": "Criadores de conteúdo", "requirement_type": "audience", "mandatory": False},
        "Público-alvo: criadores de conteúdo, filmmakers e fotógrafos.",
    )
    assert kind == "context_signal"
    assert role == "audience_context"
    assert occurrence_role == "context"


def test_product_feature_fragment_is_attribute():
    kind, role, occurrence_role = _classify(
        {"title": "Captura em alta velocidade", "requirement_type": "product", "mandatory": False},
        "Foco do produto: câmera com captura em alta velocidade.",
    )
    assert kind == "attribute_signal"
    assert role == "product_attribute"
    assert occurrence_role == "attribute"


def test_explicit_obligation_remains_requirement_candidate():
    kind, role, occurrence_role = _classify(
        {"title": "Garantir experiência acessível", "requirement_type": "operation", "mandatory": True},
        "A experiência deve garantir acesso para pessoas com mobilidade reduzida.",
    )
    assert kind == "requirement_candidate"
    assert role == "requirement_candidate"
    assert occurrence_role == "requirement"


def test_evidence_match_requires_material_support():
    req = {
        "title": "Garantir acesso para cadeirantes",
        "description": "A operação deve prever acesso para cadeirantes.",
        "attributes": {},
    }
    evidence = [
        {"id": "1", "content_text": "Cronograma de montagem e desmontagem"},
        {"id": "2", "content_text": "A operação deve prever acesso para cadeirantes e rota acessível."},
    ]
    best, score, _reason = _best_requirement_evidence(req, evidence)
    assert best and best["id"] == "2"
    assert score >= 0.78
