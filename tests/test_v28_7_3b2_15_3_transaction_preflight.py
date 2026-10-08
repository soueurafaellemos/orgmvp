from project_requirement_response_truth_transaction import (
    _execution_signature,
    build_transaction_preflight_from_projection,
)


def _projection(project_id, events):
    return {
        "version": "V28.7.3B2.15.2.1",
        "project_id": project_id,
        "status": "PASS_CONTRACT_VERIFIED_RESPONSE_TRUTH_PROJECTION",
        "all_checks_pass": True,
        "event_plans": events,
        "response_truth_changed": False,
        "human_review_created": False,
        "persistence_performed": False,
        "writes_performed": False,
        "cutover_approved": False,
        "safe_to_write_response_truth": False,
    }


def _event(ch="a"):
    return {
        "projected_event_id": "4b4f0c58-8a0c-5222-a627-c12239ec28fb",
        "event_signature": ch * 64,
        "requirement_id": "40433db9-3b46-4d68-9add-18eb5d479ef8",
        "requirement_entity_id": "8ee4eb4f-a7f0-4c5b-a3af-20e1cca5f3a1",
        "evidence_links": [{"evidence_unit_id": "7bfc9e2f-1bb6-416e-b9a8-f54034964e47"}],
    }


def test_jovi_zero_event_is_no_transaction():
    p = "01415104-72f2-4b8e-aeca-2dd24c231a7d"
    r = build_transaction_preflight_from_projection(
        project_id=p,
        projection=_projection(p, []),
    )
    assert r["status"] == "NO_TRANSACTION_REQUIRED"
    assert r["ready_for_probe"] is False
    assert r["ready_for_real_write"] is False


def test_positive_is_probe_only():
    p = "0d9f1608-4bf7-4fd0-81ab-f303fdb0c136"
    r = build_transaction_preflight_from_projection(
        project_id=p,
        projection=_projection(p, [_event()]),
    )
    assert r["status"] == "READY_FOR_ROLLBACK_ONLY_PROBE"
    assert r["ready_for_probe"] is True
    assert r["ready_for_real_write"] is False
    assert r["review_fingerprint"] == r["execution_signature"]


def test_signature_is_order_independent():
    p = "p"
    a = _event("a")
    b = dict(_event("b"))
    b["projected_event_id"] = "faaf9a44-b8ed-5f9d-933b-5688d35e4819"
    assert _execution_signature(p, [a, b]) == _execution_signature(p, [b, a])


def test_preflight_has_no_rpc():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    s = (root / "project_requirement_response_truth_transaction.py").read_text()
    assert ".rpc(" not in s


def test_ui_exposes_no_real_write():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    s = (root / "pages/44_Response_Truth_Transaction_Preflight.py").read_text()
    assert "apply_contract_verified_response_truth_b2153" not in s
    assert "SEM WRITE" in s
