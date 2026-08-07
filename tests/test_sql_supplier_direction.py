from pathlib import Path


def test_supplier_page_uses_recognized_supplier_direction():
    source = (Path(__file__).resolve().parents[1] / "pages/5_Cobertura_de_Fornecedores.py").read_text(encoding="utf-8")
    assert "_recognized_supplier_ids" in source
    assert "supplier_id not in recognized_ids" in source
    assert 'recognized_as_supplier' in source


def test_venue_operator_alone_does_not_create_supplier_visibility():
    source = (Path(__file__).resolve().parents[1] / "pages/5_Cobertura_de_Fornecedores.py").read_text(encoding="utf-8")
    assert "operar um local não basta" in source
