from pathlib import Path


def test_branding_promotes_cover_tables_to_multirow_and_pdf_from_one_item():
    source = (Path(__file__).parents[1] / "branding.py").read_text(encoding="utf-8")
    assert 'kwargs.get("selection_mode") == "single-row"' in source
    assert 'kwargs["selection_mode"] = "multi-row"' in source
    assert 'len(valid_rows) >= 1' in source
    assert '"Exportar seleção em PDF"' in source
    assert 'build_selection_pdf' in source


def test_branding_maps_specialized_tables_to_pdf_contexts():
    source = (Path(__file__).parents[1] / "branding.py").read_text(encoding="utf-8")
    for label in ("Brinde", "Ativação", "Local", "Fornecedor"):
        assert label in source
    for context in ("Brindes", "Ativações", "Locais e espaços", "Fornecedores"):
        assert context in source
