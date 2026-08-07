from pathlib import Path


def test_branding_promotes_cover_tables_to_multirow_and_pdf():
    source = (Path(__file__).parents[1] / "branding.py").read_text(encoding="utf-8")
    assert 'kwargs.get("selection_mode") == "single-row"' in source
    assert 'kwargs["selection_mode"] = "multi-row"' in source
    assert 'len(valid_rows) >= 2' in source
    assert '"Exportar seleção em PDF"' in source
    assert 'build_selection_pdf' in source


def test_pdf_understands_specialized_table_names():
    source = (Path(__file__).parents[1] / "selection_pdf.py").read_text(encoding="utf-8")
    assert 'if "Brinde" in record' in source
    assert 'if "Ativação" in record' in source
    assert '"Brinde", "Ativação", "Local", "Fornecedor"' in source
