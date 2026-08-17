from pathlib import Path

from project_core_semantic_extractor import extract_explicit_core_signals


def test_last_starting_point_is_atomic():
    text = """PONTOS DE PARTIDA
CONEXÃO
Um espaço que estimula
conexão entre pais e filhos
MEMÓRIA AFETIVA
Adultos relembram suas infâncias
resgatando memórias afetivas da marca
PRESENÇA E ATENÇÃO
Espaço e ativações desenvolvidas para
estimular a imaginação e a presença"""
    rows = {
        s.observed_name: s
        for s in extract_explicit_core_signals(text)
        if s.semantic_role == "strategic_principle"
    }
    assert rows["PRESENÇA E ATENÇÃO"].statement == (
        "Espaço e ativações desenvolvidas para\n"
        "estimular a imaginação e a presença"
    )


def test_b3_sql_scopes_a_observations_and_active_unsupported_only():
    root = Path(__file__).parents[1]
    sql = (root / "NAVE_V28_7_2B3_SEMANTIC_SCOPE_ATOMICITY.sql").read_text(encoding="utf-8").casefold()
    assert "domain_hint not in ('strategy','creative','experience','journey')" in sql
    assert "t.lifecycle_status='active' and t.truth_state='unsupported'" in sql
    assert "drop table" not in sql
    assert "delete from" not in sql
    assert "domain_primary" not in sql
