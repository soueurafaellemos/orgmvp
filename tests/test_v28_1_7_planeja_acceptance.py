from __future__ import annotations

from io import BytesIO
import sys
import types

import pytest
from openpyxl import Workbook


# Runtime connectors are available in deploy, but the patch must remain testable
# in a lean local container.
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


from memory_cost_parser import parse_cost_workbook
from project_batch_ingestion import classify_document
from project_workspace_intelligence import build_project_intelligence


def _xlsx_bytes(sheet_rows: dict[str, list[list[object]]]) -> bytes:
    wb = Workbook()
    first = True
    for name, rows in sheet_rows.items():
        if first:
            ws = wb.active
            ws.title = name
            first = False
        else:
            ws = wb.create_sheet(name)
        for row in rows:
            ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_detailed_cost_spreadsheet_wins_over_incidental_post_event_words():
    role, confidence, reasons = classify_document(
        "BRADESCO_PLANEJA 2027_13.07 .xlsx",
        """
        Abertura de Custos | Tipo Faturamento | Quantidade | Valor Unit | Valor Total |
        Honorários | Encargos | Total com Honorários e Encargos.
        Serviço de book pós-evento e relatório final incluído no escopo.
        """,
    )
    assert role == "detailed_costs"
    assert confidence >= 0.95
    assert any("custos" in reason for reason in reasons)


def test_preliminary_budget_filename_is_not_confused_with_detailed_proposal():
    role, confidence, _ = classify_document(
        "Estudo de verba Bradesco - Planeja 27.xlsx",
        "Budget 1700000 Criação FEE Impostos Técnica Atrações Brindes Serviços",
    )
    assert role == "preliminary_budget"
    assert confidence >= 0.95


def test_preliminary_budget_matrix_reconciles_without_fake_subtotals():
    data = _xlsx_bytes({
        "Estudo de verba": [
            ["Budget", 1_700_000, 1.0],
            ["Criação", 51_000, 0.03],
            ["FEE", 153_000, 0.09],
            ["Impostos", 297_500, 0.175],
            ["LOCAÇÃO DE ESPAÇO", 0, 0.0],
            ["CENOGRAFIA E INFRAESTRUTURA", 416_500, 0.245],
            ["OPERAÇÃO DE A&B", 0, 0.0],
            ["TÉCNICA", 178_500, 0.105],
            ["ATRAÇÕES", 68_000, 0.04],
            ["TAXAS", 0, 0.0],
            ["MATERIAIS | BRINDES", 93_500, 0.055],
            ["SERVIÇOS", 136_000, 0.08],
            ["EQUIPE E VERBAS", 306_000, 0.18],
            ["Sub Total", 1_700_000, 1.0],
        ]
    })
    parsed = parse_cost_workbook("Estudo de verba Bradesco - Planeja 27.xlsx", data)
    assert parsed.metadata["cost_kind"] == "preliminary_budget"
    assert parsed.client_total == pytest.approx(1_700_000)
    assert parsed.metadata["allocation_total"] == pytest.approx(1_700_000)
    assert parsed.metadata["allocation_percentage_total"] == pytest.approx(1.0)
    assert len(parsed.items) == 12
    assert all(item.item_name not in {"Budget", "Sub Total"} for item in parsed.items)


def test_detailed_cost_parser_preserves_main_total_and_separate_sheet():
    headers = [
        "ITEM", "DESCRIÇÃO", "TIPO FATURAMENTO", "QTD", "VALOR UNITÁRIO",
        "VALOR TOTAL", "HONORÁRIOS", "ENCARGOS", "TOTAL COM HONORÁRIOS E ENCARGOS",
    ]
    data = _xlsx_bytes({
        "Evento": [
            headers,
            ["CENOGRAFIA E INFRAESTRUTURA", "CENOGRAFIA E INFRAESTRUTURA", None, None, None, None, None, None, None],
            [None, "Palco", "NF", 1, 1_000_000, 1_000_000, 100_000, 200_000, 1_300_000],
            ["TOTAL", None, None, None, None, 1_000_000, 100_000, 200_000, 1_300_000],
        ],
        "Empresas": [
            headers,
            [None, "Sala Empresas", "NF", 1, 200_000, 200_000, 20_000, 30_000, 250_000],
            ["TOTAL", None, None, None, None, 200_000, 20_000, 30_000, 250_000],
        ],
    })
    parsed = parse_cost_workbook("BRADESCO_PLANEJA 2027_13.07 .xlsx", data)
    assert parsed.metadata["cost_kind"] == "detailed_costs"
    assert parsed.sheet_name == "Evento"
    assert parsed.client_total == pytest.approx(1_300_000)
    assert [item.item_name for item in parsed.items] == ["Palco"]
    assert parsed.metadata["additional_sheet_totals"][0]["sheet_name"] == "Empresas"
    assert parsed.metadata["additional_sheet_totals"][0]["client_total"] == pytest.approx(250_000)


def test_semantic_sanitizer_drops_fake_stage_from_master_of_ceremonies_page():
    from project_bundle_materializer import _sanitize_memory_items

    page_inventory = [{
        "page_number": 35,
        "text": "Mestre de Cerimônias Jéssica Leão. Atua com presença de palco, comunicação clara e carisma.",
    }]
    cleaned = _sanitize_memory_items([
        {
            "section_key": "scenography",
            "title": "Palco",
            "summary": "presença de palco, comunicação clara e carisma",
            "source_page": 35,
        }
    ], page_inventory=page_inventory)
    assert cleaned == []


def test_semantic_sanitizer_keeps_stage_card_as_communication_material():
    from project_bundle_materializer import _sanitize_memory_items

    page_inventory = [{
        "page_number": 34,
        "text": "Ficha de Palco",
    }]
    cleaned = _sanitize_memory_items([
        {
            "section_key": "scenography",
            "title": "Palco",
            "summary": "Ficha de Palco",
            "source_page": 34,
        }
    ], page_inventory=page_inventory)
    assert len(cleaned) == 1
    assert cleaned[0]["title"] == "Ficha de palco"
    assert cleaned[0]["section_key"] == "communication"


def test_intelligence_never_adds_preliminary_study_to_detailed_proposal():
    snapshot = {
        "project": {"status": "apresentado"},
        "outcome": {"budget_amount": 1_700_000},
        "project_files": [],
        "briefing_documents": [],
        "memory_documents": [],
        "feedback_entries": [],
        "report_analyses": [],
        "briefing_requirements": [],
        "briefing_links": [],
        "memory_items": [],
        "item_outcomes": [],
        "cost_links": [],
        "cost_documents": [
            {
                "id": "detailed",
                "file_name": "BRADESCO_PLANEJA 2027_13.07 .xlsx",
                "client_total": 2_435_028.72,
                "metadata": {
                    "document_role": "detailed_costs",
                    "additional_sheet_totals": [
                        {"sheet_name": "Empresas", "client_total": 248_294.02},
                    ],
                },
            },
            {
                "id": "prelim",
                "file_name": "Estudo de verba Bradesco - Planeja 27.xlsx",
                "client_total": 1_700_000,
                "metadata": {"document_role": "preliminary_budget"},
            },
        ],
        "cost_items": [
            {"id": "c1", "cost_document_id": "detailed", "category": "Infraestrutura", "item_name": "Palco", "client_total": 1_000_000},
            {"id": "c2", "cost_document_id": "detailed", "category": "Artístico", "item_name": "Palestrantes", "client_total": 1_435_028.72},
            {"id": "p1", "cost_document_id": "prelim", "category": "Estudo de verba", "item_name": "Cenografia", "client_total": 416_500},
        ],
    }
    intelligence = build_project_intelligence(snapshot)
    metrics = intelligence["metrics"]
    assert metrics["budget_amount"] == pytest.approx(1_700_000)
    assert metrics["cost_total"] == pytest.approx(2_435_028.72)
    assert metrics["preliminary_budget_total"] == pytest.approx(1_700_000)
    assert metrics["budget_delta"] == pytest.approx(-735_028.72)
    assert metrics["budget_usage_pct"] == pytest.approx(2_435_028.72 / 1_700_000)
    assert metrics["cost_items"] == 2
    assert metrics["preliminary_cost_items"] == 1
    assert metrics["additional_cost_sheets"][0]["client_total"] == pytest.approx(248_294.02)


def test_visual_dedupe_consolidates_repeated_semantic_entity():
    from project_workspace_visuals import _dedupe_visual_records

    records = [
        {"title": "Palco", "section": "scenography", "summary": "vista 1", "image_path": None, "costs": [], "briefings": []},
        {"title": "Palco", "section": "scenography", "summary": "vista principal", "image_path": "renders/palco.png", "costs": [], "briefings": []},
    ]
    deduped = _dedupe_visual_records(records)
    assert len(deduped) == 1
    assert deduped[0]["image_path"] == "renders/palco.png"
    assert deduped[0]["related_evidence_count"] == 2


def test_visual_dedupe_preserves_distinct_real_views_of_same_solution():
    from project_workspace_visuals import _dedupe_visual_records

    records = [
        {"kind": "item", "title": "Palco", "section": "scenography", "context_key": "grand_ballroom", "summary": "vista frontal", "image_path": "renders/palco_1.png", "costs": [], "briefings": []},
        {"kind": "item", "title": "Palco", "section": "scenography", "context_key": "grand_ballroom", "summary": "vista lateral", "image_path": "renders/palco_2.png", "costs": [], "briefings": []},
    ]
    deduped = _dedupe_visual_records(records)
    assert len(deduped) == 2
    assert {row["image_path"] for row in deduped} == {"renders/palco_1.png", "renders/palco_2.png"}


def test_visual_dedupe_collapses_duplicate_plan_pages_only():
    from project_workspace_visuals import _dedupe_visual_records

    records = [
        {"kind": "page", "item_type": "Implantação / planta", "title": "Planta — Grand Ballroom I & II", "section": "scenography", "context_key": "grand_ballroom", "summary": "foyer", "image_path": "renders/planta_16.png", "costs": [], "briefings": []},
        {"kind": "page", "item_type": "Implantação / planta", "title": "Planta — Grand Ballroom I & II", "section": "scenography", "context_key": "grand_ballroom", "summary": "plenária", "image_path": "renders/planta_27.png", "costs": [], "briefings": []},
    ]
    deduped = _dedupe_visual_records(records)
    assert len(deduped) == 1
    assert deduped[0]["related_evidence_count"] == 2


def test_reprocess_repairs_old_post_event_role_from_real_workbook_structure():
    from project_bundle_materializer import _repair_financial_source_role

    headers = [
        "ITEM", "DESCRIÇÃO", "TIPO FATURAMENTO", "QTD", "VALOR UNITÁRIO",
        "VALOR TOTAL", "HONORÁRIOS", "ENCARGOS", "TOTAL COM HONORÁRIOS E ENCARGOS",
    ]
    workbook = _xlsx_bytes({
        "Evento": [
            headers,
            [None, "Book pós-evento e relatório final", "NF", 1, 1000, 1000, 100, 200, 1300],
            ["TOTAL", None, None, None, None, 1000, 100, 200, 1300],
        ]
    })

    class _Response:
        data = []

    class _Query:
        def update(self, *_args, **_kwargs):
            return self
        def eq(self, *_args, **_kwargs):
            return self
        def execute(self):
            return _Response()
        def select(self, *_args, **_kwargs):
            return self
        def limit(self, *_args, **_kwargs):
            return self
        def insert(self, *_args, **_kwargs):
            return self

    class _StorageBucket:
        def download(self, _path):
            return workbook

    class _Storage:
        def from_(self, _bucket):
            return _StorageBucket()

    class _Client:
        storage = _Storage()
        def table(self, _name):
            return _Query()

    warnings = []
    fixed = _repair_financial_source_role(
        _Client(),
        {
            "id": "source-1",
            "file_name": "BRADESCO_PLANEJA 2027_13.07 .xlsx",
            "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "document_role": "post_event_report",
            "text_excerpt": "book pós-evento relatório final",
            "storage_bucket": "nave-project-files",
            "storage_path": "projects/p/planilha.xlsx",
        },
        warnings,
    )
    assert fixed["document_role"] == "detailed_costs"
    assert fixed["role_confidence"] == pytest.approx(0.99)
    assert any("post_event_report" in warning and "detailed_costs" in warning for warning in warnings)
