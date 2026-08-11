from __future__ import annotations

from io import BytesIO
import sys
import types

import fitz
import pytest
from openpyxl import Workbook

# Mantém o módulo testável no container enxuto usado para regressão.
if "supabase" not in sys.modules:
    supabase_stub = types.ModuleType("supabase")
    supabase_stub.Client = object
    sys.modules["supabase"] = supabase_stub

if "streamlit" not in sys.modules:
    streamlit_stub = types.ModuleType("streamlit")
    streamlit_stub.session_state = {}
    sys.modules["streamlit"] = streamlit_stub

try:
    import google
except ImportError:
    google = types.ModuleType("google")
    sys.modules["google"] = google
if not hasattr(google, "genai"):
    google.genai = types.SimpleNamespace(Client=object)

from document_io import InputDocument
from memory_cost_parser import parse_cost_workbook
from project_batch_ingestion import classify_document


def _xlsx_bytes(rows: list[list[object]]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Custos"
    for row in rows:
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_generic_pdf_with_proposal_structure_is_classified_as_presentation():
    role, confidence, reasons = classify_document(
        "PDF_LANCAMENTO_30.06.pdf",
        """
        Conceito criativo. Estratégia da experiência. Cenografia e implantação.
        Ativação de lançamento. Jornada do participante. Comunicação e key visual.
        """,
    )
    assert role == "proposal_presentation"
    assert confidence >= 0.65
    assert any("PDF" in reason for reason in reasons)


def test_docx_with_briefing_structure_is_classified_as_briefing():
    role, confidence, reasons = classify_document(
        "VOE_B_06.docx",
        """
        Objetivo do projeto. Desafio. Público alvo. Escopo e entregáveis.
        Obrigatoriedades, prazo e verba disponível.
        """,
    )
    assert role == "briefing_original"
    assert confidence >= 0.65
    assert any("briefing" in reason.lower() for reason in reasons)


def test_cost_parser_finds_total_at_end_of_long_sheet():
    headers = [
        "ITEM", "DESCRIÇÃO", "QTD", "VALOR UNITÁRIO", "VALOR TOTAL",
        "HONORÁRIOS", "ENCARGOS", "TOTAL COM HONORÁRIOS E ENCARGOS",
    ]
    rows = [headers]
    for index in range(1, 20):
        rows.append([index, f"Item {index}", 1, 100, 100, 10, 5, 115])
    rows.append(["TOTAL GERAL", None, None, None, 1900, 190, 95, 2185])
    parsed = parse_cost_workbook("JOVI_X300.xlsx", _xlsx_bytes(rows))
    assert parsed.client_total == pytest.approx(2185)


def test_cost_parser_reconciles_explicit_components_when_client_total_is_blank():
    data = _xlsx_bytes([
        ["ITEM", "DESCRIÇÃO", "QTD", "VALOR UNITÁRIO", "VALOR TOTAL", "HONORÁRIOS", "ENCARGOS", "TOTAL CLIENTE"],
        [1, "Cenografia", 1, 1000, 1000, 100, 50, None],
        [2, "Operação", 1, 500, 500, 50, 25, None],
    ])
    parsed = parse_cost_workbook("JOVI_X300.xlsx", data)
    assert [item.client_total for item in parsed.items] == pytest.approx([1150, 575])
    assert parsed.client_total == pytest.approx(1725)


def test_large_pdf_batch_can_be_compacted_for_ai_without_changing_original():
    from memory_extractor import _compact_pdf_for_ai

    pdf = fitz.open()
    page = pdf.new_page(width=900, height=1200)
    page.insert_text((72, 100), "PROPOSTA JOVI X300 — CENOGRAFIA E ATIVAÇÕES", fontsize=22)
    original = pdf.tobytes()
    pdf.close()
    doc = InputDocument(name="proposta.pdf", data=original, mime_type="application/pdf")

    compacted = _compact_pdf_for_ai(doc, max_bytes=1)
    assert compacted.mime_type == "application/pdf"
    assert compacted.original_data == original
    opened = fitz.open(stream=compacted.data, filetype="pdf")
    try:
        assert opened.page_count == 1
    finally:
        opened.close()
