from __future__ import annotations

from typing import Any, Mapping
from uuid import uuid4

from project_requirement_response_truth_transaction import (
    PROJECTION_VERSION,
    RPC_PROBE,
    build_response_truth_transaction_preflight,
)

VERSION = "V28.7.3B2.15.3P1"


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, Mapping):
        return [dict(data)]
    return [dict(row) for row in (data or []) if isinstance(row, Mapping)]


def run_response_truth_transaction_probe(
    client: Any,
    *,
    project_id: str,
) -> dict[str, Any]:
    before = build_response_truth_transaction_preflight(
        client,
        project_id=project_id,
    )

    if before.get("status") == "NO_TRANSACTION_REQUIRED":
        return {
            "version": VERSION,
            "project_id": project_id,
            "status": "NO_TRANSACTION_REQUIRED",
            "preflight": before,
            "probe_rpc_called": False,
            "rollback_independently_verified": True,
            "real_write_performed": False,
            "safe_to_write_response_truth": False,
        }

    if before.get("status") != "READY_FOR_ROLLBACK_ONLY_PROBE":
        return {
            "version": VERSION,
            "project_id": project_id,
            "status": "BLOCKED_BEFORE_PROBE",
            "preflight": before,
            "probe_rpc_called": False,
            "rollback_independently_verified": False,
            "real_write_performed": False,
            "safe_to_write_response_truth": False,
        }

    probe_run_id = str(uuid4())

    response = client.rpc(
        RPC_PROBE,
        {
            "p_project_id": project_id,
            "p_probe_run_id": probe_run_id,
            "p_confirmation_token": before["confirmation_token"],
            "p_review_fingerprint": before["review_fingerprint"],
            "p_projection_version": PROJECTION_VERSION,
            "p_execution_bundle": before["execution_bundle"],
            "p_execution_signature": before["execution_signature"],
        },
    ).execute()

    rows = _rows(response)
    if not rows:
        raise RuntimeError("B2.15.3P1 diagnostic RPC returned no result")
    rpc = rows[0]

    after = build_response_truth_transaction_preflight(
        client,
        project_id=project_id,
    )

    state_unchanged = (
        after.get("status") == before.get("status")
        and after.get("execution_signature") == before.get("execution_signature")
        and after.get("review_fingerprint") == before.get("review_fingerprint")
        and after.get("projected_event_count") == before.get("projected_event_count")
        and after.get("projected_evidence_link_count")
            == before.get("projected_evidence_link_count")
    )

    rollback_verified = (
        rpc.get("rollback_guaranteed") is True
        and rpc.get("real_write_performed") is False
        and state_unchanged
        and after.get("status") == "READY_FOR_ROLLBACK_ONLY_PROBE"
    )

    rpc_status = str(rpc.get("status") or "")
    if not rollback_verified:
        status = "PROBE_RETURNED_BUT_ROLLBACK_NOT_INDEPENDENTLY_VERIFIED"
    elif rpc_status == "WRITER_WOULD_COMPLETE_ROLLED_BACK":
        status = "WRITER_PATH_SUCCEEDED_BUT_WAS_FORCED_ROLLBACK"
    elif rpc_status == "WRITER_FAILED_ROLLED_BACK":
        status = "ROOT_CAUSE_CAPTURED_ROLLBACK_VERIFIED"
    else:
        status = "UNEXPECTED_PROBE_STATUS"

    return {
        "version": VERSION,
        "project_id": project_id,
        "status": status,
        "probe_run_id": probe_run_id,
        "rpc": rpc,
        "preflight_before": before,
        "preflight_after": after,
        "state_unchanged": state_unchanged,
        "rollback_independently_verified": rollback_verified,
        "probe_rpc_called": True,
        "real_write_performed": False,
        "safe_to_write_response_truth": False,
    }
