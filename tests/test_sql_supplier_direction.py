from pathlib import Path

SQL = (Path(__file__).resolve().parents[1] / "supabase_patch_v28_0_3_2_fornecedores_direcionais.sql").read_text(encoding="utf-8").lower()


def test_sql_does_not_delete_or_move_records():
    assert "delete from" not in SQL
    assert "update public.venues" not in SQL
    assert "update public.suppliers" not in SQL


def test_sql_uses_directional_venue_rule():
    assert "v.operator_id = s.id" in SQL
    assert "operates_differently_named_venue" in SQL
    assert "has_supplier_evidence" in SQL
