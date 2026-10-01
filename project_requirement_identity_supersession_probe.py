from __future__ import annotations

"""NAVE V28.7.3B2.12.5.3 — rollback-only transactional probe."""

from typing import Any, Mapping
from uuid import uuid4

from project_requirement_supersession_failure_diagnostic import (
    diagnose_failed_supersession,
)

VERSION = "V28.7.3B2.12.5.3"
RPC = "diagnose_project_requirement_identity_supersession_b21253"
WRITER_VERSION = "V28.7.3B2.12.5.1"
PROMOTION_VERSION = "V28.7.2C0.2.4H3.1.3P1"


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, Mapping):
        return [dict(data)]
    return [dict(row) for row in (data or []) if isinstance(row, Mapping)]


def _critical_state(diagnostic: Mapping[str, Any]) -> dict[str, Any]:
    old = diagnostic.get("superseded_candidate") or {}
    survivor = diagnostic.get("survivor") or {}
    return {
        "classification": diagnostic.get("classification"),
        "current_requirement_count": diagnostic.get("current_requirement_count"),
        "canonical_collision_count": diagnostic.get("canonical_collision_count"),
        "requirements_read_mode": diagnostic.get("requirements_read_mode"),
        "survivor_truth_state": survivor.get("truth_state"),
        "survivor_requirement_status": survivor.get("requirement_status"),
        "old_truth_state": old.get("truth_state"),
        "old_requirement_status": old.get("requirement_status"),
        "old_governance_lifecycle": old.get("governance_lifecycle"),
        "old_knowledge_entity_status": old.get("knowledge_entity_status"),
        "writer_source_evidence_links_found": diagnostic.get(
            "writer_source_evidence_links_found"
        ),
        "writer_occurrence_evidence_links_found": diagnostic.get(
            "writer_occurrence_evidence_links_found"
        ),
        "latest_matching_writer_run": diagnostic.get("latest_matching_writer_run"),
    }


def run_rollback_only_transaction_probe(
    client: Any,
    *,
    preflight: Mapping[str, Any],
) -> dict[str, Any]:
    project_id = str(preflight.get("project_id") or "")
    version = str(preflight.get("version") or "")
    status = str(preflight.get("status") or "")
    fingerprint = str(preflight.get("review_fingerprint") or "")
    token = str(preflight.get("confirmation_token") or "")
    bundle = preflight.get("execution_bundle")
    signature = str(preflight.get("execution_signature") or "")
    contract = preflight.get("pipeline_contract") or {}

    blockers: list[str] = []

    if version != WRITER_VERSION:
        blockers.append(f"preflight_version_expected_{WRITER_VERSION}_got_{version}")
    if status != "READY_FOR_EXPLICIT_TRANSACTION":
        blockers.append(f"preflight_not_ready_status_{status}")
    if preflight.get("ready_for_write") is not True:
        blockers.append("preflight_ready_for_write_not_true")
    if preflight.get("blockers"):
        blockers.append("preflight_contains_blockers")
    if not project_id:
        blockers.append("project_id_missing")
    if len(fingerprint) != 64:
        blockers.append("review_fingerprint_invalid")
    if token != f"SUPERSEDE:{project_id}:{fingerprint[:12]}":
        blockers.append("confirmation_token_not_bound_to_fingerprint")
    if not isinstance(bundle, Mapping):
        blockers.append("execution_bundle_missing")
    if not signature:
        blockers.append("execution_signature_missing")
    if str(contract.get("promotion_version") or "") != PROMOTION_VERSION:
        blockers.append("promotion_contract_mismatch")
    if contract.get("normal_pipeline_uses_h31") is not True:
        blockers.append("normal_pipeline_h31_not_active")

    if blockers:
        return {
            "version": VERSION,
            "project_id": project_id or None,
            "status": "BLOCKED_BEFORE_PROBE",
            "blockers": blockers,
            "probe_rpc_called": False,
            "real_write_performed": False,
            "safe_to_run_real_writer": False,
        }

    before = diagnose_failed_supersession(client, preflight=preflight)
    if before.get("classification") != "CONFIRMED_PREWRITE_STATE_INTACT":
        return {
            "version": VERSION,
            "project_id": project_id,
            "status": "BLOCKED_PREWRITE_STATE_NOT_INTACT",
            "blockers": [
                f"pre_probe_state={before.get('classification')}"
            ],
            "pre_probe_state": before,
            "probe_rpc_called": False,
            "real_write_performed": False,
            "safe_to_run_real_writer": False,
        }

    probe_run_id = str(uuid4())
    response = client.rpc(
        RPC,
        {
            "p_project_id": project_id,
            "p_probe_run_id": probe_run_id,
            "p_confirmation_token": token,
            "p_review_fingerprint": fingerprint,
            "p_pipeline_promotion_version": PROMOTION_VERSION,
            "p_execution_bundle": bundle,
            "p_execution_signature": signature,
        },
    ).execute()

    rows = _rows(response)
    if not rows:
        raise RuntimeError("B2.12.5.3 diagnostic RPC returned no result")

    rpc_result = rows[0]

    after = diagnose_failed_supersession(client, preflight=preflight)

    before_critical = _critical_state(before)
    after_critical = _critical_state(after)
    state_unchanged = before_critical == after_critical
    rollback_verified = (
        after.get("classification") == "CONFIRMED_PREWRITE_STATE_INTACT"
        and state_unchanged
        and rpc_result.get("rollback_guaranteed") is True
        and rpc_result.get("real_write_performed") is False
    )

    status = str(rpc_result.get("status") or "")
    if not rollback_verified:
        final_status = "PROBE_RETURNED_BUT_ROLLBACK_NOT_INDEPENDENTLY_VERIFIED"
    elif status == "WRITER_FAILED_ROLLED_BACK":
        final_status = "ROOT_CAUSE_CAPTURED_ROLLBACK_VERIFIED"
    elif status == "WRITER_WOULD_COMPLETE_ROLLED_BACK":
        final_status = "WRITER_PATH_SUCCEEDED_BUT_WAS_FORCED_ROLLBACK"
    else:
        final_status = "UNEXPECTED_PROBE_STATUS"

    return {
        "version": VERSION,
        "project_id": project_id,
        "status": final_status,
        "review_fingerprint": fingerprint,
        "probe_run_id": probe_run_id,
        "rpc": rpc_result,
        "pre_probe_critical_state": before_critical,
        "post_probe_critical_state": after_critical,
        "state_unchanged": state_unchanged,
        "rollback_independently_verified": rollback_verified,
        "probe_rpc_called": True,
        "real_write_performed": False,
        "safe_to_run_real_writer": False,
        "next_action": (
            "Fix the captured database root cause before any real writer retry."
            if status == "WRITER_FAILED_ROLLED_BACK"
            else
            "Review the successful rollback-only path before authorizing a real writer run."
        ),
    }
