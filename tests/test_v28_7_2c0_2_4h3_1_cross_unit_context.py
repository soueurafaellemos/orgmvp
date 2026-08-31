from __future__ import annotations

from project_requirement_semantic_h31 import cross_unit_section_role, _surrounding_by_evidence_h31, _is_section_boundary


def test_cross_unit_audience_fragment_is_context():
    role = cross_unit_section_role(
        "Frequentadores de festivais de música;",
        "Frequentadores de festivais de música;",
        "Público-Alvo Principal – X300 Ultra:\nCriadores de conteúdo;",
    )
    assert role == "audience_context"


def test_cross_unit_platform_fragment_is_scope():
    role = cross_unit_section_role(
        "Storytelling detalhado.",
        "Storytelling detalhado.",
        "Adequação à Plataforma - O YouTube é o ambiente ideal para:\nConteúdo de longa duração;\nReviews técnicos aprofundados;",
    )
    assert role == "platform_scope"


def test_cross_unit_first_example_is_example_signal():
    role = cross_unit_section_role(
        "Mini show ao vivo;",
        "Mini show ao vivo;",
        "A experiência deve permitir que os convidados testem o kit em um ambiente dinâmico, como:",
    )
    assert role == "example_signal"


def test_cross_unit_second_example_keeps_parent_across_sibling_unit():
    role = cross_unit_section_role(
        "Performance com muito movimento;",
        "Performance com muito movimento;",
        "A experiência deve permitir que os convidados testem o kit em um ambiente dinâmico, como:\nMini show ao vivo;",
    )
    assert role == "example_signal"


def test_cross_unit_requirement_parent_remains_requirement_parent():
    role = cross_unit_section_role(
        "Iluminação premium para retratos.",
        "Iluminação premium para retratos.",
        "A ativação deve explorar:",
    )
    assert role == "requirement_parent"


def test_nearer_current_section_beats_older_platform_parent():
    role = cross_unit_section_role(
        "Espaço para plenária;",
        "O local deve contemplar:\nEspaço para plenária;",
        "Adequação à Plataforma - O YouTube é o ambiente ideal para:\nStorytelling detalhado.",
    )
    assert role == "requirement_parent"


def test_compact_new_heading_stops_stale_parent_inheritance():
    role = cross_unit_section_role(
        "Item nominal isolado",
        "Item nominal isolado",
        "Público-Alvo:\nCriadores de conteúdo\nInformações logísticas:\nSão Paulo",
    )
    assert role is None


def test_cross_unit_parent_survives_more_than_three_sibling_units():
    role = cross_unit_section_role(
        "Frequentadores de festivais de música;",
        "Frequentadores de festivais de música;",
        "A proposta deve estar fortemente conectada ao nosso público-alvo principal:\n"
        "Criadores de conteúdo;\n"
        "Filmmakers;\n"
        "Fotógrafos;",
    )
    assert role == "audience_context"


def test_platform_parent_survives_three_preceding_bullets():
    role = cross_unit_section_role(
        "Storytelling detalhado.",
        "Storytelling detalhado.",
        "Adequação à Plataforma - O YouTube é o ambiente ideal para:\n"
        "Conteúdo de longa duração;\n"
        "Reviews técnicos aprofundados;\n"
        "Tutoriais de alta produção;",
    )
    assert role == "platform_scope"


def test_same_line_platform_parent_is_recognized():
    role = cross_unit_section_role(
        "Storytelling detalhado.",
        "Adequação à Plataforma - O YouTube é o ambiente ideal para: Storytelling detalhado.",
        "",
    )
    assert role == "platform_scope"


def test_h31_surrounding_window_reaches_fourth_previous_unit():
    rows = [
        {"id": "parent", "ordinal": 1, "is_current": True, "content_text": "A proposta deve estar fortemente conectada ao nosso público-alvo principal:"},
        {"id": "one", "ordinal": 2, "is_current": True, "content_text": "Criadores de conteúdo;"},
        {"id": "two", "ordinal": 3, "is_current": True, "content_text": "Filmmakers;"},
        {"id": "three", "ordinal": 4, "is_current": True, "content_text": "Fotógrafos;"},
        {"id": "target", "ordinal": 5, "is_current": True, "content_text": "Frequentadores de festivais de música;"},
    ]
    source = {"evidence_by_asset": {"asset": rows}}
    context = _surrounding_by_evidence_h31(source, {"asset"})["target"]
    assert context.startswith("A proposta deve estar fortemente conectada")
    assert "Fotógrafos;" in context


def test_unpunctuated_objective_section_stops_stale_audience_inheritance():
    role = cross_unit_section_role(
        "Objetivo principal",
        "Objetivo principal: O projeto consiste em criarmos o espaço patrocinado pela marca.",
        "PUBLICO ALVO:\nMães e pais entre 30 e 45 anos\nCrianças de 2 a 12 anos\nOBJETIVO E DESAFIO",
    )
    assert role is None


def test_unpunctuated_deliverables_heading_stops_stale_platform_inheritance():
    role = cross_unit_section_role(
        "Cobertura de foto e vídeo",
        "Cobertura de foto e vídeo",
        "Adequação à Plataforma - O YouTube é o ambiente ideal para:\n"
        "Storytelling detalhado.\n"
        "ENTREGAVEIS",
    )
    assert role is None


def test_common_briefing_heading_without_colon_is_section_boundary():
    assert _is_section_boundary("OBJETIVO E DESAFIO") is True
    assert _is_section_boundary("RESULTADO ESPERADO") is True
    assert _is_section_boundary("ENTREGAVEIS") is True


def test_uppercase_bullet_is_not_a_boundary_by_style_alone():
    assert _is_section_boundary("MINI SHOW AO VIVO") is False


def test_explicit_requirement_parent_still_wins_before_boundary_guard():
    role = cross_unit_section_role(
        "Iluminação premium para retratos.",
        "Iluminação premium para retratos.",
        "Público-Alvo:\nCriadores de conteúdo\nA ativação deve explorar:",
    )
    assert role == "requirement_parent"
