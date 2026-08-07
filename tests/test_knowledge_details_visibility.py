from knowledge_details import _is_missing, visible_fields, visible_sections


def test_missing_sentinels_are_hidden_but_zero_and_false_are_kept():
    for value in (None, "", "Não informado", "NAO INFORMADO", "N/A", "—", "sem informação"):
        assert _is_missing(value)
    assert not _is_missing(0)
    assert not _is_missing(False)


def test_empty_section_disappears():
    record = {"name": "Ativação XP", "description": "", "base_price": "Não informado"}
    sections = visible_sections("activation", record)
    titles = [title for title, _ in sections]
    assert "Identificação" in titles
    assert "Valores e condições" not in titles


def test_raw_data_can_surface_value_without_not_informed_noise():
    record = {"name": "Brinde", "raw_data": {"category": "Tecnologia"}}
    fields = visible_fields([("category", "Categoria"), ("description", "Descrição")], record)
    assert fields == [("category", "Categoria")]
