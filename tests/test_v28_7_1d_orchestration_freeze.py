from pathlib import Path


def test_finalizer_freezes_v286_graph_and_runs_reconciliation_then_domain_audits():
    code = (Path(__file__).parents[1] / "project_intelligence_pipeline.py").read_text(encoding="utf-8")
    assert '"status": "frozen_v28_6"' in code
    assert "ensure_project_source_evidence" in code
    assert "sync_project_domain_normalization" in code
    assert "reconcile_project_domain" in code
    assert "run_project_domain_truth_audits" in code
    assert code.index("ensure_project_source_evidence") < code.index("sync_project_domain_normalization") < code.index("reconcile_project_domain") < code.index("run_project_domain_truth_audits")
    assert "materialize_project_canonical_entities" not in code
    assert "run_project_cross_source_intelligence" not in code
    assert "analyze_project_snapshot" not in code
    assert '"semantic_project_analysis": None' in code


def test_ui_success_depends_on_truth_reconciliation_and_audits_not_cross_source():
    code = (Path(__file__).parents[1] / "pages" / "14_Importar_Projeto.py").read_text(encoding="utf-8")
    assert 'domain_ok = str(domain.get("status") or "") == "completed"' in code
    assert 'reconciliation_ok = str(reconciliation.get("status") or "") == "completed"' in code
    assert 'audits_ok = str(audits.get("status") or "") == "completed"' in code
    assert "if domain_ok and reconciliation_ok and audits_ok and core_ok:" in code
    assert "Graph V28.6 continuou congelado" in code
    assert "cross_ok" not in code
    assert "Reconciliar Core Semantic Domains · V28.7.2B" in code
    assert "Conflitos de identidade para revisão" in code


def test_schema_probe_requires_v2871d_truth_objects():
    code = (Path(__file__).parents[1] / "project_domain_normalization.py").read_text(encoding="utf-8")
    assert '"entity_outcome_truth_status"' in code
    assert '"outcomes_legacy_unverified"' in code
    assert 'NORMALIZATION_RPC = "apply_project_domain_normalization_v2871d"' in code
