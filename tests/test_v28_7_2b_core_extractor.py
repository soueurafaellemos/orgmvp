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


def test_adjacent_pillars_stop_at_new_explicit_section_heading_and_do_not_leak_resources():
    from project_core_semantic_extractor import _adjacent_explicit_group_signals

    evidence = [
        {"id": "h", "source_asset_id": "a", "ordinal": 20, "unit_type": "paragraph", "content_text": "Pilares:"},
        {"id": "p1", "source_asset_id": "a", "ordinal": 21, "unit_type": "paragraph", "content_text": "Resgate da infância - Sabor de marca"},
        {"id": "p2", "source_asset_id": "a", "ordinal": 22, "unit_type": "paragraph", "content_text": "Conexão familiar entre pais e filhos – Casa e brincadeiras"},
        {"id": "p3", "source_asset_id": "a", "ordinal": 23, "unit_type": "paragraph", "content_text": "Imaginação e memórias"},
        {"id": "p4", "source_asset_id": "a", "ordinal": 24, "unit_type": "paragraph", "content_text": "Coração"},
        {"id": "section", "source_asset_id": "a", "ordinal": 25, "unit_type": "paragraph", "content_text": "Canais oficiais:"},
        {"id": "url1", "source_asset_id": "a", "ordinal": 26, "unit_type": "paragraph", "content_text": "Site da marca: https://example.com/"},
        {"id": "url2", "source_asset_id": "a", "ordinal": 27, "unit_type": "paragraph", "content_text": "YouTube: https://youtube.com/example"},
    ]
    result = _adjacent_explicit_group_signals(evidence)
    assert set(result) == {"p1", "p2", "p3", "p4"}
    assert "section" not in result
    assert "url1" not in result
    assert "url2" not in result


def test_adjacent_pillar_with_colon_and_body_remains_a_valid_group_item():
    from project_core_semantic_extractor import _adjacent_explicit_group_signals

    evidence = [
        {"id": "h", "source_asset_id": "a", "ordinal": 1, "unit_type": "paragraph", "content_text": "Pilares:"},
        {"id": "p", "source_asset_id": "a", "ordinal": 2, "unit_type": "paragraph", "content_text": "Inovação: simplificar a experiência sem perder relevância."},
        {"id": "stop", "source_asset_id": "a", "ordinal": 3, "unit_type": "paragraph", "content_text": "Entregáveis:"},
    ]
    result = _adjacent_explicit_group_signals(evidence)
    assert result["p"][0]["semantic_role"] == "pillar"
    assert result["p"][0]["observed_name"] == "Inovação"
    assert "stop" not in result


def test_same_page_starting_points_keep_atomic_statements_between_visual_headings():
    signals = extract_explicit_core_signals(
        "PONTOS DE PARTIDA\n"
        "CONEXÃO\nUm espaço que estimula conexão entre pais e filhos\n"
        "MEMÓRIA AFETIVA\nAdultos relembram suas infâncias e a marca\n"
        "PRESENÇA E ATENÇÃO\nEspaço e ativações estimulam imaginação e presença"
    )
    by_name = {s.observed_name: s for s in signals if s.domain_hint == "strategy" and s.semantic_role == "strategic_principle"}
    assert by_name["CONEXÃO"].statement == "Um espaço que estimula conexão entre pais e filhos"
    assert by_name["MEMÓRIA AFETIVA"].statement == "Adultos relembram suas infâncias e a marca"
    assert by_name["PRESENÇA E ATENÇÃO"].statement == "Espaço e ativações estimulam imaginação e presença"


def test_starting_points_last_heading_keeps_local_body_until_page_end():
    text = """PONTOS DE PARTIDA
CONEXÃO
Um espaço que estimula
conexão entre pais e filhos
MEMÓRIA AFETIVA
Adultos relembram suas infâncias
resgatando memórias afetivas da marca
PRESENÇA E ATENÇÃO
Espaço e ativações desenvolvidas para
estimular a imaginação e a presença"""
    signals = extract_explicit_core_signals(text)
    rows = {s.observed_name: s for s in signals if s.semantic_role == "strategic_principle"}
    assert rows["CONEXÃO"].statement == "Um espaço que estimula\nconexão entre pais e filhos"
    assert rows["MEMÓRIA AFETIVA"].statement == "Adultos relembram suas infâncias\nresgatando memórias afetivas da marca"
    assert rows["PRESENÇA E ATENÇÃO"].statement == "Espaço e ativações desenvolvidas para\nestimular a imaginação e a presença"
    assert "PONTOS DE PARTIDA" not in rows["PRESENÇA E ATENÇÃO"].statement



def test_meta_headings_are_not_promoted_as_strategy_territory():
    signals = extract_explicit_core_signals(
        "HIGHLIGHTS\n"
        "1. The market is competitive.\n"
        "2. Each player owns a distinct territory of differentiation.\n"
        "3. Audiences are loyal."
    )
    assert not any(s.semantic_role == "territory" for s in signals)

    signals = extract_explicit_core_signals(
        "INSIGHT\n"
        "Within this landscape, we will build on a territory the brand already owns "
        "and make it relevant to Brazil."
    )
    assert any(s.semantic_role == "insight" for s in signals)
    assert not any(s.semantic_role == "territory" for s in signals)


def test_named_heading_can_still_be_explicit_territory_by_referential_language():
    signals = extract_explicit_core_signals(
        "NOSTALGIA\n"
        "Vamos nos apropriar desse território para resgatar memórias afetivas."
    )
    territories = [s for s in signals if s.domain_hint == "strategy" and s.semantic_role == "territory"]
    assert len(territories) == 1
    assert territories[0].observed_name == "NOSTALGIA"


def test_bare_journey_copy_does_not_create_experience_architecture():
    signals = extract_explicit_core_signals(
        "EVENT\nPRODUCT REVEAL\nSTEP 1\n"
        "AN INVITATION\nTO THE\nJOURNEY\n"
        "Connects to the “On Tour” idea, a creative journey that begins here."
    )
    assert any(s.domain_hint == "creative" and s.semantic_role == "big_idea" and "On Tour" in s.observed_name for s in signals)
    assert not any(s.domain_hint == "experience" and s.semantic_role == "experience_architecture" for s in signals)


def test_specific_event_journey_still_creates_architecture_and_stages():
    signals = extract_explicit_core_signals(
        "EVENT JOURNEY\n"
        "1. PRE-EVENT\nGuest communications\n"
        "2. EVENT\nOfficial launch day\n"
        "3. POST-EVENT\nThank-you message"
    )
    assert any(s.domain_hint == "experience" and s.observed_name == "EVENT JOURNEY" for s in signals)
    stage_types = {
        (s.attributes or {}).get("moment_type")
        for s in signals
        if s.domain_hint == "journey" and s.semantic_role == "stage"
    }
    assert {"pre_event", "event", "post_event"} <= stage_types


def test_adjacent_strategic_heading_stops_before_audience_or_new_guideline_section():
    from project_core_semantic_extractor import _adjacent_strategic_signals

    evidence = [
        {"id": "h1", "source_asset_id": "a", "ordinal": 1, "unit_type": "paragraph", "content_text": "Alinhamento Estratégico:"},
        {"id": "aud", "source_asset_id": "a", "ordinal": 2, "unit_type": "paragraph", "content_text": "A proposta deve estar conectada ao público-alvo principal:"},
        {"id": "aud2", "source_asset_id": "a", "ordinal": 3, "unit_type": "paragraph", "content_text": "Frequentadores de festivais de música;"},
        {"id": "h2", "source_asset_id": "a", "ordinal": 10, "unit_type": "paragraph", "content_text": "Objetivos Estratégicos para a marca:"},
        {"id": "good", "source_asset_id": "a", "ordinal": 11, "unit_type": "paragraph", "content_text": "Demonstrar superioridade das câmeras por meio de experiências práticas;"},
        {"id": "stop", "source_asset_id": "a", "ordinal": 12, "unit_type": "paragraph", "content_text": "Diretrizes de Ativação por Plataforma – abaixo temos os direcionais:"},
        {"id": "after", "source_asset_id": "a", "ordinal": 13, "unit_type": "paragraph", "content_text": "TikTok: usar movimento e tendências."},
    ]
    result = _adjacent_strategic_signals(evidence)
    assert "aud2" not in result
    assert "good" in result
    assert "stop" not in result
    assert "after" not in result


def test_audience_scoped_strategic_heading_does_not_promote_audience_bullets():
    evidence = [
        {"id": "h", "source_asset_id": "a", "ordinal": 10,
         "content_text": "Alinhamento Estratégico:\nA proposta deve estar fortemente conectada ao nosso público-alvo principal:"},
        {"id": "a1", "source_asset_id": "a", "ordinal": 11, "content_text": "Criadores de conteúdo;"},
        {"id": "a2", "source_asset_id": "a", "ordinal": 12, "content_text": "Filmmakers;"},
        {"id": "a3", "source_asset_id": "a", "ordinal": 13, "content_text": "Fotógrafos;"},
        {"id": "a4", "source_asset_id": "a", "ordinal": 14, "content_text": "Frequentadores de festivais de música;"},
        {"id": "stop", "source_asset_id": "a", "ordinal": 15, "content_text": "Ativações e Experiências por Plataforma:"},
    ]
    result = _adjacent_strategic_signals(evidence)
    assert result == {}


def test_separate_audience_boundary_still_stops_adjacent_strategy():
    evidence = [
        {"id": "h", "source_asset_id": "a", "ordinal": 1, "content_text": "Alinhamento Estratégico:"},
        {"id": "boundary", "source_asset_id": "a", "ordinal": 2,
         "content_text": "A proposta deve estar conectada ao público-alvo principal:"},
        {"id": "a", "source_asset_id": "a", "ordinal": 3, "content_text": "Frequentadores de festivais de música;"},
    ]
    result = _adjacent_strategic_signals(evidence)
    assert result == {}
