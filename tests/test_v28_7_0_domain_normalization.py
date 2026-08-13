from pathlib import Path

from project_domain_normalization import (
    _cost_state,
    _group_memory_items,
    _item_outcome_semantics,
    _paid_by,
    _proposal_execution_status,
    solution_kind_from_legacy,
)


def test_domain_normalization_consolidates_duplicate_memory_occurrences():
    rows = [
        {"id": "a", "section_key": "gifts", "item_type": "Brinde", "title": "Press kit", "summary": "PRESS KIT"},
        {"id": "b", "section_key": "gifts", "item_type": "Brinde", "title": "Press kit", "summary": "Composição do press kit"},
        {"id": "c", "section_key": "gifts", "item_type": "Brinde", "title": "Meias", "summary": "Meias personalizadas"},
    ]
    grouped = _group_memory_items(rows)
    assert len(grouped) == 2
    press = [items for _, kind, items in grouped if kind == "presskit"]
    assert len(press) == 1
    assert {row["id"] for row in press[0]} == {"a", "b"}


def test_workshop_is_activation_even_if_legacy_section_is_gifts():
    row = {
        "section_key": "gifts",
        "item_type": "Brinde / kit",
        "title": "Oficinas Criativas",
        "description": "Oficina de criação nas mesas laterais com entrega de brindes.",
    }
    assert solution_kind_from_legacy(row) == "activation"


def test_presskit_is_container_not_generic_gift():
    row = {
        "section_key": "gifts",
        "item_type": "Brinde / kit",
        "title": "Press kit",
        "description": "Kit para influenciadores e seeding.",
    }
    assert solution_kind_from_legacy(row) == "presskit"


def test_legacy_status_separates_proposal_from_execution():
    assert _proposal_execution_status({"item_status": "Proposto"}) == ("proposed", "not_confirmed")
    assert _proposal_execution_status({"item_status": "Aprovado"}) == ("approved", "not_confirmed")
    assert _proposal_execution_status({"item_status": "Executado"}) == ("unknown", "executed")


def test_financial_state_and_payment_responsibility_are_preserved():
    assert _cost_state({"item_status": "optional", "estimate_type": "quoted"}) == "optional"
    assert _cost_state({"item_status": "pending", "estimate_type": "waiting_supplier"}) == "pending"
    assert _paid_by({"item_status": "client_responsibility"}) == "client"
    assert _paid_by({"item_status": "included"}) == "unknown"


def test_outcome_semantics_do_not_conflate_execution_and_approval():
    assert _item_outcome_semantics("executed") == ("execution_status", "executed")
    assert _item_outcome_semantics("approved") == ("proposal_status", "approved")
    assert _item_outcome_semantics("not_approved") == ("proposal_status", "rejected")
    assert _item_outcome_semantics("unassessed") is None


def test_sql_creates_only_the_domain_foundation_objects_for_this_phase():
    sql_path = Path(__file__).parents[1] / "NAVE_V28_7_0_DOMAIN_NORMALIZATION_FOUNDATION.sql"
    sql = sql_path.read_text(encoding="utf-8")
    for table in (
        "project_solution_instances",
        "project_requirements",
        "financial_documents",
        "financial_line_items",
        "entity_outcomes",
    ):
        assert f"create table if not exists public.{table}" in sql
    assert "drop table" not in sql.casefold()
    assert "delete from public.memory_" not in sql.casefold()
    assert "project_domain_normalization_status" in sql
    assert "entity_current_outcomes" in sql
