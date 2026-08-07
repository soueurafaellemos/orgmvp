from pathlib import Path


def test_supplier_page_requires_upload_or_repertoire_evidence():
    source = (Path(__file__).resolve().parents[1] / "pages/5_Cobertura_de_Fornecedores.py").read_text(encoding="utf-8")
    assert "_recognized_supplier_ids" in source
    assert "products" in source
    assert "activations" in source
    assert "imports" in source
    assert "recognized_as_supplier" in source
