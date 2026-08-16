from pathlib import Path


def test_finalizer_freezes_v286_graph_and_runs_domain_audits():
    code = (Path(__file__).parents[1] / "project_intelligence_pipeline.py").read_text(encoding="utf-8")
    assert '"status": "frozen_v28_6"' in code
    assert "run_project_domain_truth_audits" in code
    assert "sync_project_domain_normalization" in code
    assert "materialize_project_canonical_entities" not in code
    assert "run_project_cross_source_intelligence" not in code
    assert "analyze_project_snapshot" not in code
    assert '"semantic_project_analysis": None' in code


def test_ui_success_depends_on_domain_and_audits_not_cross_source():
    code = (Path(__file__).parents[1] / "pages" / "14_Importar_Projeto.py").read_text(encoding="utf-8")
    assert 'domain_ok = str(domain.get("status") or "") == "completed"' in code
    assert 'audits_ok = str(audits.get("status") or "") == "completed"' in code
    assert "if domain_ok and audits_ok:" in code
    assert "Graph V28.6 permaneceu congelado" in code
    assert "cross_ok" not in code
    assert "Atualizar domínio e auditar verdade" in code
    assert "Possíveis soluções ausentes do domínio" in code
    assert "Conflitos de identidade para revisão" in code


def test_schema_probe_requires_v2871d_truth_objects():
    code = (Path(__file__).parents[1] / "project_domain_normalization.py").read_text(encoding="utf-8")
    assert '"entity_outcome_truth_status"' in code
    assert '"outcomes_legacy_unverified"' in code
    assert 'NORMALIZATION_RPC = "apply_project_domain_normalization_v2871d"' in code
