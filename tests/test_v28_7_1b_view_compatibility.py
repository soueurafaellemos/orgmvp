from pathlib import Path
import re


def _view_columns(sql: str, view_name: str):
    pattern = rf"create or replace view public\.{re.escape(view_name)}.*?select distinct on \(entity_id, outcome_type\)(.*?)from public\.entity_outcomes"
    m = re.search(pattern, sql, flags=re.I | re.S)
    assert m, f"view {view_name} not found"
    body = m.group(1)
    return [x.strip().strip(',') for x in body.splitlines() if x.strip() and not x.strip().startswith('--')]


def test_entity_current_outcomes_preserves_v2870_prefix_and_appends_event_status():
    root = Path(__file__).parents[1]
    new_sql = (root / 'NAVE_V28_7_1B_DOMAIN_INTEGRITY_SQL_COMPAT.sql').read_text(encoding='utf-8')
    old_cols = [
        'id', 'entity_id', 'project_id', 'outcome_type', 'outcome_status',
        'outcome_at', 'reason', 'source_claim_id', 'source_evidence_id',
        'confidence', 'authority_score', 'is_human_confirmed', 'attributes',
        'created_at',
    ]
    new_cols = _view_columns(new_sql, 'entity_current_outcomes')
    assert new_cols[: len(old_cols)] == old_cols
    assert new_cols[len(old_cols):] == ['event_status']


def test_sql_contains_explicit_view_layout_self_check():
    root = Path(__file__).parents[1]
    sql = (root / 'NAVE_V28_7_1B_DOMAIN_INTEGRITY_SQL_COMPAT.sql').read_text(encoding='utf-8').casefold()
    assert "column_name = 'created_at'" in sql
    assert 'ordinal_position = 14' in sql
    assert "column_name = 'event_status'" in sql
    assert 'ordinal_position = 15' in sql
