from pathlib import Path


def test_supplier_view_excludes_venue_only_operators():
    sql = (
        Path(__file__).resolve().parents[1]
        / "supabase_patch_v28_0_3_1_fornecedores_visibilidade.sql"
    ).read_text(encoding="utf-8").lower()

    assert "create or replace view public.supplier_coverage_overview" in sql
    assert "from public.venues v_filter" in sql
    assert "from public.products p_filter" in sql
    assert "from public.activation_solutions a_filter" in sql
    assert "where not (" in sql
    assert "and not exists" in sql
