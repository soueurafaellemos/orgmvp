from pathlib import Path


def test_normal_pipeline_selects_h31_not_base_h3():
    root = Path(__file__).resolve().parents[1]
    source = (root / "project_intelligence_pipeline.py").read_text(encoding="utf-8")
    assert "project_requirement_reconciliation_h31" in source
    assert 'from project_requirement_reconciliation import reconcile_project_requirements' not in source


def test_pipeline_has_read_only_promotion_contract():
    root = Path(__file__).resolve().parents[1]
    source = (root / "project_intelligence_pipeline.py").read_text(encoding="utf-8")
    assert "def requirement_reconciliation_contract" in source
    assert '"pipeline_run_triggered_by_promotion": False' in source
    assert '"graph_rebuild_triggered_by_promotion": False' in source


def test_repair_page_no_longer_claims_pipeline_is_old_h3():
    root = Path(__file__).resolve().parents[1]
    source = (root / "pages/33_Requirement_Semantic_Truth_Repair.py").read_text(encoding="utf-8")
    assert "pipeline normal continua em H3" not in source
    assert "entrypoint oficial" in source


def test_promotion_verifier_never_calls_finalize_pipeline():
    root = Path(__file__).resolve().parents[1]
    source = (root / "pages/36_Requirement_Pipeline_Promotion_Verifier.py").read_text(encoding="utf-8")
    assert "finalize_project_intelligence(" not in source
    assert "verify_requirement_pipeline_promotion" in source
