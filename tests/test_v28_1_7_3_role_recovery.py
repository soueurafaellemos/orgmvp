from __future__ import annotations

import sys
import types

if "supabase" not in sys.modules:
    supabase_stub = types.ModuleType("supabase")
    supabase_stub.Client = object
    sys.modules["supabase"] = supabase_stub

if "streamlit" not in sys.modules:
    streamlit_stub = types.ModuleType("streamlit")
    streamlit_stub.session_state = {}
    streamlit_stub.secrets = {}
    sys.modules["streamlit"] = streamlit_stub

try:
    import google
except ImportError:
    google = types.ModuleType("google")
    sys.modules["google"] = google
if not hasattr(google, "genai"):
    google.genai = types.SimpleNamespace(Client=object)

import project_bundle_materializer as materializer


def _fake_role_setter(client, source_file, *, role, confidence, reasons, warnings):
    row = dict(source_file)
    old = row.get("document_role")
    row["document_role"] = role
    row["role_confidence"] = confidence
    row["role_reasons"] = list(reasons)
    warnings.append(f"{old} -> {role}")
    return row


def test_topology_recovers_docx_briefing_and_pdf_proposal_even_from_wrong_historical_roles(monkeypatch):
    monkeypatch.setattr(materializer, "_set_source_document_role", _fake_role_setter)
    rows = [
        {"id": "1", "file_name": "VOE_B_06 (1).docx", "document_role": "post_event_report", "text_excerpt": "", "page_count": None},
        {"id": "2", "file_name": "PDF_LANCAMENTO_30.06.pdf", "document_role": "supplier_reference", "text_excerpt": "", "page_count": None},
        {"id": "3", "file_name": "JOVI_X300.xlsx", "document_role": "detailed_costs", "text_excerpt": "", "page_count": None},
        {"id": "4", "file_name": "feedback.jpeg", "document_role": "feedback_approval", "text_excerpt": "", "page_count": None},
    ]
    warnings = []
    repaired = materializer._repair_bundle_topology(None, rows, warnings)
    by_id = {row["id"]: row for row in repaired}
    assert by_id["1"]["document_role"] == "briefing_original"
    assert by_id["2"]["document_role"] == "proposal_presentation"
    assert by_id["3"]["document_role"] == "detailed_costs"
    assert by_id["4"]["document_role"] == "feedback_approval"
    assert warnings


def test_topology_does_not_guess_presentation_when_two_pdfs_exist(monkeypatch):
    monkeypatch.setattr(materializer, "_set_source_document_role", _fake_role_setter)
    rows = [
        {"id": "1", "file_name": "brief.docx", "document_role": "briefing_original"},
        {"id": "2", "file_name": "a.pdf", "document_role": "complementary_document"},
        {"id": "3", "file_name": "b.pdf", "document_role": "complementary_document"},
        {"id": "4", "file_name": "cost.xlsx", "document_role": "detailed_costs"},
    ]
    repaired = materializer._repair_bundle_topology(None, rows, [])
    assert [r["document_role"] for r in repaired if r["file_name"].endswith(".pdf")] == [
        "complementary_document", "complementary_document"
    ]


def test_briefing_materialization_falls_back_to_preserved_text_when_storage_unavailable(monkeypatch):
    monkeypatch.setattr(materializer, "_sync_project_file", lambda *args, **kwargs: True)
    monkeypatch.setattr(materializer, "_ensure_project_file_role", lambda *args, **kwargs: None)
    monkeypatch.setattr(materializer, "_download_bytes", lambda *args, **kwargs: None)
    marked = {}
    monkeypatch.setattr(materializer, "_mark_source_file", lambda client, sid, **kwargs: marked.update(kwargs))
    monkeypatch.setattr(materializer, "_materialize_briefing", lambda client, source, text, warnings: {"briefing_documents": 1, "briefing_requirements": 3})

    result = materializer.materialize_source_file(None, {
        "id": "brief-1",
        "project_id": "project-1",
        "file_name": "brief.docx",
        "document_role": "briefing_original",
        "text_excerpt": "Objetivo do projeto. Público alvo. Entregáveis e obrigatoriedades.",
        "sha256": "abc",
    }, force_semantic_reprocess=True)
    assert result.status == "materialized_with_warnings"
    assert result.created["briefing_documents"] == 1
    assert any("trecho textual" in warning for warning in result.warnings)


def test_presentation_materialization_falls_back_to_preserved_text_when_storage_unavailable(monkeypatch):
    monkeypatch.setattr(materializer, "_sync_project_file", lambda *args, **kwargs: True)
    monkeypatch.setattr(materializer, "_ensure_project_file_role", lambda *args, **kwargs: None)
    monkeypatch.setattr(materializer, "_download_bytes", lambda *args, **kwargs: None)
    monkeypatch.setattr(materializer, "_mark_source_file", lambda *args, **kwargs: None)
    monkeypatch.setattr(materializer, "_materialize_presentation", lambda client, source, text, warnings: {"memory_documents": 1, "memory_items": 5})

    result = materializer.materialize_source_file(None, {
        "id": "pdf-1",
        "project_id": "project-1",
        "file_name": "proposal.pdf",
        "document_role": "proposal_presentation",
        "text_excerpt": "Estratégia. Conceito. Cenografia. Ativações. Comunicação.",
        "sha256": "def",
    }, force_semantic_reprocess=True)
    assert result.status == "materialized_with_warnings"
    assert result.created["memory_documents"] == 1
    assert result.created["memory_items"] == 5
    assert any("workspace vazio" in warning for warning in result.warnings)
