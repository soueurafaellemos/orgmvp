from pathlib import Path


def test_confirmation_is_bound_to_reviewed_fingerprint():
    root = Path(__file__).resolve().parents[1]
    source = (root / "project_requirement_identity_supersession.py").read_text(encoding="utf-8")
    assert "review_fingerprint" in source
    assert "fresh_fingerprint != reviewed_fingerprint" in source
    assert 'f"SUPERSEDE:{project_id}:{review_fingerprint[:12]}"' in source


def test_rpc_is_not_executable_by_public():
    root = Path(__file__).resolve().parents[1]
    sql = (
        root / "NAVE_V28_7_3B2_12_5_GOVERNED_TRANSACTIONAL_REQUIREMENT_IDENTITY_SUPERSESSION.sql"
    ).read_text(encoding="utf-8").lower()
    assert "from public, anon, authenticated" in sql
    assert "to service_role" in sql
    assert "p_review_fingerprint text" in sql


def test_old_six_arg_rpc_is_removed():
    root = Path(__file__).resolve().parents[1]
    sql = (
        root / "NAVE_V28_7_3B2_12_5_GOVERNED_TRANSACTIONAL_REQUIREMENT_IDENTITY_SUPERSESSION.sql"
    ).read_text(encoding="utf-8").lower()
    assert "drop function if exists public.apply_project_requirement_identity_supersession_b2125" in sql


def test_ui_passes_reviewed_fingerprint_to_writer():
    root = Path(__file__).resolve().parents[1]
    source = (root / "pages/37_Governed_Requirement_Identity_Supersession.py").read_text(encoding="utf-8")
    assert "reviewed_fingerprint=reviewed_fingerprint" in source
    assert "review_fingerprint=" in source
