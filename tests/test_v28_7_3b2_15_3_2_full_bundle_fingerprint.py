from pathlib import Path


def test_python_preflight_calls_server_bundle_fingerprint():
    root = Path(__file__).resolve().parents[1]
    s = (root / "project_requirement_response_truth_transaction.py").read_text()
    assert "inspect_response_truth_bundle_b21532" in s
    assert "entire_jsonb_execution_bundle" in s
    assert "baseline_sha256" in s


def test_sql_fingerprints_entire_bundle_and_recomputes_in_writer():
    root = Path(__file__).resolve().parents[1]
    s = (
        root / "NAVE_V28_7_3B2_15_3_2_FULL_BUNDLE_FINGERPRINT_HARDENING.sql"
    ).read_text().lower()

    assert "response_truth_bundle_fingerprint_b21532" in s
    assert "coalesce(p_execution_bundle, '{}'::jsonb)::text" in s
    assert "public.response_truth_bundle_fingerprint_b21532(p_execution_bundle)" in s
    assert "full-bundle reviewed fingerprint/signature mismatch" in s


def test_bootstrap_writer_exact_scope():
    root = Path(__file__).resolve().parents[1]
    s = (
        root / "NAVE_V28_7_3B2_15_3_2_FULL_BUNDLE_FINGERPRINT_HARDENING.sql"
    ).read_text().lower()

    assert "0d9f1608-4bf7-4fd0-81ab-f303fdb0c136" in s
    assert "424a9c0a7992c99a7a37117784d7304ecb86033431e40d8687171a20286264d2" in s
    assert "requires exactly 3 events" in s
    assert "requires exactly 3 evidence links" in s
    assert "expected 13" in s
    assert "shadow_compare" in s


def test_old_rpcs_dropped_and_side_effect_scope_stays_narrow():
    root = Path(__file__).resolve().parents[1]
    s = (
        root / "NAVE_V28_7_3B2_15_3_2_FULL_BUNDLE_FINGERPRINT_HARDENING.sql"
    ).read_text().lower()

    assert "drop function if exists public.diagnose_contract_verified_response_truth_b2153" in s
    assert "drop function if exists public.apply_contract_verified_response_truth_b2153" in s

    assert "insert into public.intelligence_reviews" not in s
    assert "insert into public.domain_object_evidence" not in s
    assert "update public.project_requirements" not in s
    assert "delete from public." not in s

    assert "insert into public.project_requirement_response_truth_events" in s
    assert "insert into public.project_requirement_response_truth_evidence" in s
