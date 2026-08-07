from pathlib import Path

from project_ingestion_db import _project_row_for_matching


def test_current_projects_schema_is_mapped_to_identity_fields():
    row = {
        "id": "project-1",
        "project_name": "Bradesco — Planeja 27",
        "client_brand": "Bradesco",
        "event_name": "Planeja 27",
        "event_date": "2026-11-30",
        "location_city": "Atibaia",
        "location_state": "SP",
        "audience_quantity": 250,
        "budget_total_brl": 1700000,
        "raw_data": {
            "event_end": "2026-12-04",
            "venue_name": "Bourbon Atibaia Resort",
            "reference_year": 2027,
            "edition": "27",
            "keywords": ["Varejo", "Prime", "Empresas"],
        },
    }

    mapped = _project_row_for_matching(row)

    assert mapped["project_id"] == "project-1"
    assert mapped["event_start"] == "2026-11-30"
    assert mapped["event_end"] == "2026-12-04"
    assert mapped["city"] == "Atibaia"
    assert mapped["state"] == "SP"
    assert mapped["audience_size"] == 250
    assert mapped["budget_amount"] == 1700000
    assert mapped["venue_name"] == "Bourbon Atibaia Resort"
    assert mapped["reference_year"] == 2027
    assert mapped["edition"] == "27"


def test_event_date_is_used_as_safe_end_date_fallback():
    mapped = _project_row_for_matching(
        {
            "id": "project-2",
            "project_name": "Projeto simples",
            "event_date": "2026-10-15",
            "raw_data": {},
        }
    )

    assert mapped["event_start"] == "2026-10-15"
    assert mapped["event_end"] == "2026-10-15"


def test_sql_uses_real_projects_columns():
    sql_path = (
        Path(__file__).resolve().parents[1]
        / "supabase_patch_v28_0_2_identidade_projetos.sql"
    )
    sql = sql_path.read_text(encoding="utf-8")

    required = (
        "project.event_date",
        "project.location_city",
        "project.location_state",
        "project.audience_quantity",
        "project.budget_total_brl",
    )
    forbidden = (
        "project.event_date_start",
        "project.event_date_end",
        "project.city",
        "project.state",
        "project.audience_size",
        "project.budget_amount",
    )

    for fragment in required:
        assert fragment in sql

    for fragment in forbidden:
        assert fragment not in sql


def test_python_fallback_does_not_query_nonexistent_columns():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "project_ingestion_db.py"
    )
    source = module_path.read_text(encoding="utf-8")

    assert '.select("*")' in source
    assert '"event_date_start,event_date_end' not in source
    assert '"audience_size,budget_amount' not in source
