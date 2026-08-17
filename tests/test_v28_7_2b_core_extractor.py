from project_core_semantic_extractor import (
    _adjacent_strategic_signals,
    extract_explicit_core_signals,
)


def _keys(signals):
    return {(s.domain_hint, s.semantic_role, s.observed_name) for s in signals}


def test_chambinho_style_source_extracts_explicit_pillars_territory_and_pov_without_journey():
    pillars = extract_explicit_core_signals(
        "MEMÓRIA AFETIVA\nCONEXÃO\nPRESENÇA E ATENÇÃO\nPONTOS DE PARTIDA\n"
        "Um espaço que estimula conexão entre pais e filhos"
    )
    keys = _keys(pillars)
    assert ("strategy", "strategic_principle", "MEMÓRIA AFETIVA") in keys
    assert ("strategy", "strategic_principle", "CONEXÃO") in keys
    assert ("strategy", "strategic_principle", "PRESENÇA E ATENÇÃO") in keys
    assert not any(s.domain_hint in {"experience", "journey"} for s in pillars)

    territory = extract_explicit_core_signals(
        "NOSTALGIA\nVamos nos apropriar desse território tão característico da marca."
    )
    assert any(s.domain_hint == "strategy" and s.semantic_role == "territory" and s.observed_name == "NOSTALGIA" for s in territory)

    pov = extract_explicit_core_signals(
        "POINT OF VIEW\nEM 2026 VAMOS APROVEITAR O SEU GRANDE BOOM PARA CRIAR A CASA MAIS NOSTALGICA DE TODAS."
    )
    assert any(s.domain_hint == "creative" and s.semantic_role == "pov" and "CASA MAIS NOSTALGICA" in s.observed_name for s in pov)


def test_jovi_style_source_extracts_explicit_journey_and_named_moments():
    journey = extract_explicit_core_signals(
        "EVENT JOURNEY\n1. PRE-EVENT\nGuest communications\n2. EVENT\nOfficial launch day\n3. POST-EVENT\nThank-you message"
    )
    keys = _keys(journey)
    assert ("experience", "experience_architecture", "EVENT JOURNEY") in keys
    assert ("journey", "stage", "PRE-EVENT") in keys
    assert ("journey", "stage", "EVENT") in keys
    assert ("journey", "stage", "POST-EVENT") in keys

    reveal = extract_explicit_core_signals("EVENT\nPRODUCT REVEAL\nIt is time to unveil the products.")
    assert any(s.domain_hint == "journey" and s.observed_name == "PRODUCT REVEAL" for s in reveal)

    activation = extract_explicit_core_signals("EVENT\nACTIVATION REVEAL\nThe activation areas will open.")
    assert any(s.domain_hint == "journey" and s.observed_name == "ACTIVATION REVEAL" for s in activation)

    idea = extract_explicit_core_signals('Connects to the “Road Story” idea, a creative journey that begins here.')
    assert any(s.domain_hint == "creative" and s.semantic_role == "big_idea" and s.observed_name == "Road Story" for s in idea)


def test_content_creation_in_body_does_not_invent_journey_moment():
    signals = extract_explicit_core_signals(
        "The most important thing is the concept of experiences focused on different forms of content creation."
    )
    assert not any(s.domain_hint == "journey" for s in signals)


def test_adjacent_strategic_heading_can_ground_following_paragraph_without_moving_evidence():
    evidence = [
        {"id": "h", "source_asset_id": "a", "ordinal": 10, "content_text": "Objetivos Estratégicos"},
        {"id": "b1", "source_asset_id": "a", "ordinal": 11, "content_text": "Demonstrar superioridade de câmera por experiências práticas."},
        {"id": "b2", "source_asset_id": "a", "ordinal": 12, "content_text": "Reforçar design e estilo premium."},
        {"id": "stop", "source_asset_id": "a", "ordinal": 13, "content_text": "Diretrizes de Ativação"},
    ]
    result = _adjacent_strategic_signals(evidence)
    assert "b1" in result and "b2" in result
    assert result["b1"][0]["attributes"]["heading_evidence_id"] == "h"
    assert "stop" not in result


def test_explicit_insight_heading_uses_source_body_without_analyst_synthesis():
    signals = extract_explicit_core_signals(
        "Within this landscape, we will build on a territory the brand already owns and make it relevant locally.\nINSIGHT"
    )
    insights = [s for s in signals if s.domain_hint == "strategy" and s.semantic_role == "insight"]
    assert len(insights) == 1
    assert "territory the brand already owns" in insights[0].statement
    assert insights[0].assertion_mode == "source_explicit"


def test_source_label_pilares_remains_pillar_while_pontos_de_partida_is_principle():
    pilares = extract_explicit_core_signals("PILARES\nINOVAÇÃO\nCONEXÃO")
    assert ("strategy", "pillar", "INOVAÇÃO") in _keys(pilares)
    assert ("strategy", "pillar", "CONEXÃO") in _keys(pilares)
    pontos = extract_explicit_core_signals("MEMÓRIA\nPRESENÇA\nPONTOS DE PARTIDA")
    assert ("strategy", "strategic_principle", "MEMÓRIA") in _keys(pontos)
    assert ("strategy", "strategic_principle", "PRESENÇA") in _keys(pontos)


def test_flattened_pdf_page_is_recoverable_to_source_explicit_starting_points_and_territory():
    # Historical Evidence Units flatten PDF page text. The semantic parser itself is
    # intentionally line-sensitive; the B1 recovery restores visual PDF line boundaries
    # before calling it.
    recovered_points = (
        "MEMÓRIA AFETIVA\nCONEXÃO\nPRESENÇA E ATENÇÃO\nPONTOS DE PARTIDA\n"
        "Um espaço que estimula conexão entre pais e filhos\n"
        "Adultos relembram suas infâncias resgatando memórias afetivas da marca\n"
        "Espaço e ativações desenvolvidas para estimular a imaginação e a presença"
    )
    keys = _keys(extract_explicit_core_signals(recovered_points))
    assert ("strategy", "strategic_principle", "MEMÓRIA AFETIVA") in keys
    assert ("strategy", "strategic_principle", "CONEXÃO") in keys
    assert ("strategy", "strategic_principle", "PRESENÇA E ATENÇÃO") in keys

    territory = extract_explicit_core_signals(
        "NOSTALGIA\nO caminho que seguimos com sutileza nas outras edições está mais em alta que nunca "
        "e vamos nos apropriar desse território tão característico da marca."
    )
    assert any(
        s.domain_hint == "strategy" and s.semantic_role == "territory" and s.observed_name == "NOSTALGIA"
        for s in territory
    )


def test_adjacent_pilares_heading_recovers_explicit_docx_group_without_synthesis():
    from project_core_semantic_extractor import _adjacent_explicit_group_signals

    evidence = [
        {"id": "h", "source_asset_id": "a", "ordinal": 33, "unit_type": "paragraph", "content_text": "Pilares:"},
        {
            "id": "p1", "source_asset_id": "a", "ordinal": 34, "unit_type": "paragraph",
            "content_text": "Resgate da infância – brincadeiras e referências afetivas.",
        },
        {
            "id": "p2", "source_asset_id": "a", "ordinal": 35, "unit_type": "paragraph",
            "content_text": "Conexão familiar entre pais e filhos – casa e brincadeiras da infância.",
        },
        {
            "id": "p3", "source_asset_id": "a", "ordinal": 36, "unit_type": "paragraph",
            "content_text": "Imaginação e memórias – experiências que convidam a criar.",
        },
        {"id": "stop", "source_asset_id": "a", "ordinal": 37, "unit_type": "paragraph", "content_text": "Diretrizes"},
    ]
    result = _adjacent_explicit_group_signals(evidence)
    assert result["p1"][0]["semantic_role"] == "pillar"
    assert result["p1"][0]["observed_name"] == "Resgate da infância"
    assert result["p2"][0]["observed_name"] == "Conexão familiar entre pais e filhos"
    assert result["p3"][0]["observed_name"] == "Imaginação e memórias"
    assert "stop" not in result


def test_pdf_layout_reader_preserves_visual_line_boundaries():
    from project_core_semantic_extractor import _pdf_layout_lines
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page(width=900, height=600)
    page.insert_text((50, 70), "MEMÓRIA AFETIVA")
    page.insert_text((300, 70), "CONEXÃO")
    page.insert_text((500, 70), "PRESENÇA E ATENÇÃO")
    page.insert_text((50, 120), "PONTOS DE PARTIDA")
    page.insert_text((50, 160), "Um espaço que estimula conexão entre pais e filhos")
    payload = doc.tobytes()
    doc.close()

    recovered = _pdf_layout_lines(payload, [1])[1]
    assert "MEMÓRIA AFETIVA" in recovered
    assert "CONEXÃO" in recovered
    assert "PRESENÇA E ATENÇÃO" in recovered
    assert "PONTOS DE PARTIDA" in recovered
    assert "\n" in recovered
