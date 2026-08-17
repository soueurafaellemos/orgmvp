from pathlib import Path

import pytest

from project_domain_normalization import _schema_error_kind


def test_pgrst205_is_schema_missing_but_generic_read_error_is_not():
    assert _schema_error_kind(Exception("{'code':'PGRST205','message':'Could not find the table public.x in the schema cache'}")) == "schema_missing"
    assert _schema_error_kind(Exception("timeout talking to PostgREST")) == "schema_check_error"


def test_pipeline_blocks_downstream_when_domain_is_unavailable_or_not_completed():
    code = (Path(__file__).parents[1] / "project_intelligence_pipeline.py").read_text(encoding="utf-8")
    assert '"status": "domain_blocked"' in code
    assert '"status": "frozen_v28_6"' in code
    assert 'if domain_status != "completed":' in code
    assert "probe_domain_schema" in code
    block = code.split("def finalize_project_intelligence", 1)[1]
    assert block.index("probe_domain_schema") < block.index("auto_analyze_pending_reports")
    assert "analyze_pending_reports: bool = True" in code


def test_ui_green_success_requires_truth_reconciliation_and_audits():
    code = (Path(__file__).parents[1] / "pages" / "14_Importar_Projeto.py").read_text(encoding="utf-8")
    assert 'domain_ok = str(domain.get("status") or "") == "completed"' in code
    assert 'reconciliation_ok = str(reconciliation.get("status") or "") == "completed"' in code
    assert 'audits_ok = str(audits.get("status") or "") == "completed"' in code
    assert 'requirement_ok = str(requirement_reconciliation.get("status") or "") == "completed"' in code
    assert "if domain_ok and reconciliation_ok and audits_ok and requirement_ok and core_ok:" in code
    assert "elif not domain_ok:" in code
    assert "analyze_pending_reports=False" in code


def test_hotfix_b_sql_self_checks_and_reloads_postgrest_schema_cache_when_fixture_is_bundled():
    path = Path(__file__).parents[1] / "NAVE_V28_7_1B_DOMAIN_INTEGRITY_SQL_COMPAT.sql"
    if not path.exists():
        pytest.skip("historical V28.7.1B SQL is intentionally not bundled in this repository export")
    sql = path.read_text(encoding="utf-8").casefold()
    assert "to_regclass('public.project_solution_occurrences')" in sql
    assert "to_regprocedure('public.apply_project_domain_normalization_v2871(uuid,uuid,jsonb)')" in sql
    assert "notify pgrst, 'reload schema'" in sql
