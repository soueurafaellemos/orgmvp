from io import BytesIO

import pytest
from openpyxl import Workbook

from memory_cost_parser import parse_cost_workbook


def _workbook_bytes(rows):
    wb = Workbook()
    ws = wb.active
    ws.title = "Verba"
    for row in rows:
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_cost_parser_does_not_turn_section_or_subtotal_into_items():
    data = _workbook_bytes([
        ["ITEM", "DESCRIÇÃO", "QTD", "VALOR UNITÁRIO", "TOTAL FINAL"],
        ["EQUIPE E VERBAS", None, None, None, None],
        [None, "Produtor executivo", 2, 1000, 2000],
        ["Sub Total", None, None, None, 2000],
    ])
    parsed = parse_cost_workbook("estudo.xlsx", data)
    assert [item.item_name for item in parsed.items] == ["Produtor executivo"]
    assert parsed.client_total == 2000


def test_cost_parser_keeps_total_unknown_when_spreadsheet_has_no_values():
    data = _workbook_bytes([
        ["ITEM", "DESCRIÇÃO", "QTD", "VALOR UNITÁRIO", "TOTAL FINAL"],
        ["EQUIPE E VERBAS", None, None, None, None],
        [None, "Produtor executivo", None, None, None],
    ])
    parsed = parse_cost_workbook("estudo.xlsx", data)
    assert parsed.client_total is None


def _semantic_module():
    try:
        from project_bundle_materializer import (
            _sanitize_memory_items,
            PROJECT_FILE_ROLE_BY_DOCUMENT_ROLE,
        )
    except ImportError as exc:
        pytest.skip(f"Dependência de runtime não instalada neste ambiente: {exc}")
    return _sanitize_memory_items, PROJECT_FILE_ROLE_BY_DOCUMENT_ROLE


def test_semantic_memory_guards():
    sanitize, _ = _semantic_module()
    cleaned = sanitize([
        {"section_key": "strategy", "title": "Vitello alla Piemontese e Panna Cotta", "summary": "Jantar temático com risotto"},
        {"section_key": "gifts", "title": "Check-in e almoço", "summary": "Check-in, almoço, plenária e jantar"},
    ])
    assert cleaned[0]["section_key"] == "content_agenda"
    assert cleaned[1]["section_key"] == "content_agenda"


def test_project_file_role_mapping_matches_workspace_roles():
    _, mapping = _semantic_module()
    assert mapping["briefing_original"] == "briefing_original"
    assert mapping["detailed_costs"] == "cost_sheet"
    assert mapping["preliminary_budget"] == "cost_sheet"
