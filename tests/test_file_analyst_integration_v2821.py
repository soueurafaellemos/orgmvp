from __future__ import annotations

from pathlib import Path


def test_materializer_has_best_effort_intelligence_dual_write():
    text = Path("project_bundle_materializer.py").read_text(encoding="utf-8")
    assert "dual_write_source_file" in text
    assert "workspace legado foi preservado" in text
    assert 'WORKFLOW_VERSION = "28.3.0"' in text


def test_import_page_exposes_current_version():
    text = Path("pages/14_Importar_Projeto.py").read_text(encoding="utf-8")
    assert "V28.3.0" in text
