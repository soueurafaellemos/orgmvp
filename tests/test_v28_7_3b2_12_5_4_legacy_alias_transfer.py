from pathlib import Path


def _sql() -> str:
    root = Path(__file__).resolve().parents[1]
    return (
        root
        / "NAVE_V28_7_3B2_12_5_4_GOVERNED_TRANSACTIONAL_REQUIREMENT_IDENTITY_SUPERSESSION.sql"
    ).read_text(encoding="utf-8")


def test_writer_and_consumers_use_5_4():
    root = Path(__file__).resolve().parents[1]
    writer = (root / "project_requirement_identity_supersession.py").read_text(encoding="utf-8")
    verifier = (root / "project_requirement_identity_supersession_verify.py").read_text(encoding="utf-8")
    probe = (root / "project_requirement_identity_supersession_probe.py").read_text(encoding="utf-8")
    assert 'VERSION = "V28.7.3B2.12.5.4"' in writer
    assert 'WRITER_VERSION = "V28.7.3B2.12.5.4"' in verifier
    assert 'WRITER_VERSION = "V28.7.3B2.12.5.4"' in probe


def test_alias_owner_released_before_survivor_binding():
    sql = _sql().lower()
    release = sql.index("set legacy_source_table = null,")
    bind = sql.index(
        "set legacy_source_table = coalesce(legacy_source_table, v_alias_source_table)"
    )
    assert release < bind
    assert "v_alias_owner_id = any(v_superseded_ids)" in sql


def test_alias_transfer_fails_closed():
    sql = _sql().lower()
    assert "legacy alias has multiple project requirement owners" in sql
    assert "legacy alias owner is not a superseded identity" in sql
    assert "failed to release legacy alias from superseded owner" in sql
    assert "failed to bind legacy alias to survivor" in sql
    assert "legacy alias target pair is still owned outside the planned transfer" in sql


def test_alias_transfer_is_audited_and_postconditioned():
    sql = _sql().lower()
    assert "legacy_alias_transfers" in sql
    assert "legacy_alias_transfer_count" in sql
    assert "survivor does not own legacy alias bridge" in sql
    assert "superseded identity still owns legacy alias bridge" in sql


def test_core_fail_closed_guards_remain():
    sql = _sql().lower()
    assert "delete from" not in sql
    assert "pg_advisory_xact_lock" in sql
    assert "shadow_compare" in sql
    assert "historical evidence links changed" in sql
    assert "historical semantic observations changed" in sql
    assert "survivor business metadata changed unexpectedly" in sql
