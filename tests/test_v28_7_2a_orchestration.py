from pathlib import Path


def test_reconciliation_runs_between_truth_baseline_and_audits():
    code = (Path(__file__).parents[1] / "project_intelligence_pipeline.py").read_text(encoding="utf-8")
    truth_pos = code.index("sync_project_domain_normalization")
    reconciliation_pos = code.index("reconcile_project_domain")
    audit_pos = code.index("run_project_domain_truth_audits")
    assert truth_pos < reconciliation_pos < audit_pos
    assert "materialize_project_canonical_entities" not in code
    assert "run_project_cross_source_intelligence" not in code
    assert '"status": "frozen_v28_6"' in code


def test_ui_requires_reconciliation_before_success():
    code = (Path(__file__).parents[1] / "pages" / "14_Importar_Projeto.py").read_text(encoding="utf-8")
    assert 'reconciliation_ok = str(reconciliation.get("status") or "") == "completed"' in code
    assert "if domain_ok and reconciliation_ok and audits_ok:" in code
    assert "Reconciliar domínio semântico · V28.7.2A" in code
    assert "Evidence → Observation → Domain" in code
