from pathlib import Path


def test_sql_is_fail_closed_and_non_destructive():
    root = Path(__file__).resolve().parents[1]
    sql = (
        root
        / "NAVE_V28_7_3B2_12_5_GOVERNED_TRANSACTIONAL_REQUIREMENT_IDENTITY_SUPERSESSION.sql"
    ).read_text(encoding="utf-8")
    lower = sql.lower()

    assert "pg_advisory_xact_lock" in sql
    assert "shadow_compare" in sql
    assert "raise exception" in lower
    assert "delete from" not in lower
    assert "response_truth_changed" in sql
    assert "'source'" in sql
    assert "only a coalesced SOURCE evidence insert is allowed" in sql


def test_writer_rebuilds_fresh_dry_run_before_rpc():
    root = Path(__file__).resolve().parents[1]
    source = (root / "project_requirement_identity_supersession.py").read_text(
        encoding="utf-8"
    )
    assert "run_hardened_dry_run" in source
    assert "Always rebuild preflight immediately before the RPC" in source
    assert "apply_project_requirement_identity_supersession_b2125" in source


def test_verifier_is_read_only_and_independent():
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "project_requirement_identity_supersession_verify.py"
    ).read_text(encoding="utf-8")
    assert ".insert(" not in source
    assert ".update(" not in source
    assert ".delete(" not in source
    assert "run_identity_collision_shadow" in source
    assert "load_requirement_compatibility" in source


def test_page_requires_explicit_token_for_real_write():
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "pages/37_Governed_Requirement_Identity_Supersession.py"
    ).read_text(encoding="utf-8")
    assert "SUPERSEDE" not in source  # token is produced by governed module, not hard-coded UI.
    assert "Token de confirmação" in source
    assert "WRITE REAL" in source
    assert "disabled=(not confirm or token != expected_token)" in source
