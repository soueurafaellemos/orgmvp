from pathlib import Path


def test_sql_scope_and_probe():
    root = Path(__file__).resolve().parents[1]
    s = (
        root / "NAVE_V28_7_3B2_15_3_CONTRACT_VERIFIED_RESPONSE_TRUTH_TRANSACTION.sql"
    ).read_text().lower()

    assert "apply_contract_verified_response_truth_b2153" in s
    assert "diagnose_contract_verified_response_truth_b2153" in s
    assert "nave_b2153_forced_rollback_after_writer_success" in s
    assert "pg_advisory_xact_lock" in s
    assert "shadow_compare" in s

    assert "insert into public.project_requirement_response_truth_events" in s
    assert "insert into public.project_requirement_response_truth_evidence" in s
    assert "insert into public.intelligence_runs" in s

    assert "update public.project_requirements" not in s
    assert "insert into public.intelligence_reviews" not in s
    assert "insert into public.domain_object_evidence" not in s
    assert "delete from public." not in s

    assert "explicit_human_confirmation" not in s
    assert "'human_confirmed_response', 'governed_response_contract'" not in s
    assert "'human_confirmed_response', 'explicit_human_confirmation'" not in s

    assert "from public, anon, authenticated" in s
    assert "to service_role" in s
