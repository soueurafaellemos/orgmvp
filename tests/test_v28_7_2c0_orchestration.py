from pathlib import Path


def test_c0_runs_after_solution_audits_and_before_core_b():
    code = (Path(__file__).parents[1] / "project_intelligence_pipeline.py").read_text(encoding="utf-8")
    truth = code.index("sync_project_domain_normalization")
    solution = code.index("reconcile_project_domain")
    audits = code.index("run_project_domain_truth_audits")
    requirements = code.index("reconcile_project_requirements")
    core = code.index("materialize_project_core_semantics")
    assert truth < solution < audits < requirements < core
    assert '"status": "requirement_reconciliation_blocked"' in code
    assert '"status": "frozen_v28_6"' in code


def test_ui_requires_c0_before_b_success_and_renders_own_debugger():
    code = (Path(__file__).parents[1] / "pages" / "14_Importar_Projeto.py").read_text(encoding="utf-8")
    assert "Requirement Semantic Reconciliation · V28.7.2C0" in code
    assert 'requirement_ok = str(requirement_reconciliation.get("status") or "") == "completed"' in code
    assert "if domain_ok and reconciliation_ok and audits_ok and requirement_ok and core_ok:" in code
    assert "Reconciliar Requirements + Core Semantics · V28.7.2C0" in code
    assert "Duas Requirement identities existentes nunca são auto-merged" in code
