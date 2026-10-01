from pathlib import Path


def test_probe_sql_is_rollback_only_wrapper():
    root = Path(__file__).resolve().parents[1]
    sql = (
        root / "NAVE_V28_7_3B2_12_5_3_ROLLBACK_ONLY_TRANSACTION_PROBE.sql"
    ).read_text(encoding="utf-8").lower()

    assert "diagnose_project_requirement_identity_supersession_b21253" in sql
    assert "apply_project_requirement_identity_supersession_b2125" in sql
    assert "nave_b21253_forced_rollback_after_writer_success" in sql
    assert "exception when others then" in sql
    assert "get stacked diagnostics" in sql
    assert "rollback_guaranteed" in sql
    assert "real_write_performed" in sql

    # The probe itself must not contain direct DML. All mutation-capable work is
    # delegated to the writer inside the rollback-only subtransaction.
    assert "insert into public." not in sql
    assert "update public." not in sql
    assert "delete from public." not in sql


def test_probe_rpc_least_privilege():
    root = Path(__file__).resolve().parents[1]
    sql = (
        root / "NAVE_V28_7_3B2_12_5_3_ROLLBACK_ONLY_TRANSACTION_PROBE.sql"
    ).read_text(encoding="utf-8").lower()
    assert "from public, anon, authenticated" in sql
    assert "to service_role" in sql


def test_python_probe_never_calls_real_writer_rpc_directly():
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "project_requirement_identity_supersession_probe.py"
    ).read_text(encoding="utf-8")
    assert 'RPC = "diagnose_project_requirement_identity_supersession_b21253"' in source
    assert 'RPC = "apply_project_requirement_identity_supersession_b2125"' not in source
    assert "diagnose_failed_supersession" in source
    assert '"safe_to_run_real_writer": False' in source


def test_probe_page_has_no_real_writer_button():
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "pages/40_Requirement_Supersession_Transaction_Probe.py"
    ).read_text(encoding="utf-8")
    assert "execute_governed_supersession" not in source
    assert "WRITE REAL" in source  # warning copy only
    assert "PROBE COM ROLLBACK OBRIGATÓRIO" in source
