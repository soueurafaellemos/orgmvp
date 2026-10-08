from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping

from project_requirement_response_truth_projection_shadow import (
    VERSION as PROJECTION_VERSION,
    run_contract_verified_response_truth_projection_shadow,
)

VERSION = "V28.7.3B2.15.3"
CONTRACT_VERSION = "V28.7.3B2.7.1"
RPC_PROBE = "diagnose_contract_verified_response_truth_b2153"


def _execution_signature(project_id: str, event_plans: list[Mapping[str, Any]]) -> str:
    signatures = sorted(str(row.get("event_signature") or "") for row in event_plans)
    return sha256(
        f"{VERSION}|{project_id}|{','.join(signatures)}".encode("utf-8")
    ).hexdigest()


def build_transaction_preflight_from_projection(
    *,
    project_id: str,
    projection: Mapping[str, Any],
) -> dict[str, Any]:
    project_id = str(project_id or "")
    blockers: list[str] = []

    if str(projection.get("version") or "") != PROJECTION_VERSION:
        blockers.append("projection_version_mismatch")
    if str(projection.get("project_id") or "") != project_id:
        blockers.append("projection_project_mismatch")
    if projection.get("all_checks_pass") is not True:
        blockers.append("projection_not_pass")
    if projection.get("status") != "PASS_CONTRACT_VERIFIED_RESPONSE_TRUTH_PROJECTION":
        blockers.append(f"projection_status_{projection.get('status')}")
    for key in (
        "response_truth_changed",
        "human_review_created",
        "persistence_performed",
        "writes_performed",
        "cutover_approved",
    ):
        if projection.get(key) is not False:
            blockers.append(f"projection_guard_{key}")
    if projection.get("safe_to_write_response_truth") is not False:
        blockers.append("projection_unexpectedly_self_authorized")

    event_plans = [
        dict(row)
        for row in (projection.get("event_plans") or [])
        if isinstance(row, Mapping)
    ]

    if blockers:
        return {
            "version": VERSION,
            "project_id": project_id,
            "status": "BLOCKED_BEFORE_TRANSACTION_PREFLIGHT",
            "blockers": blockers,
            "ready_for_probe": False,
            "ready_for_real_write": False,
            "real_write_performed": False,
        }

    if not event_plans:
        return {
            "version": VERSION,
            "project_id": project_id,
            "status": "NO_TRANSACTION_REQUIRED",
            "blockers": [],
            "projection_version": PROJECTION_VERSION,
            "contract_version": CONTRACT_VERSION,
            "projected_event_count": 0,
            "projected_evidence_link_count": 0,
            "ready_for_probe": False,
            "ready_for_real_write": False,
            "confirmation_token": None,
            "review_fingerprint": None,
            "execution_signature": None,
            "execution_bundle": None,
            "real_write_performed": False,
            "response_truth_changed": False,
        }

    event_signatures = [
        str(row.get("event_signature") or "")
        for row in event_plans
    ]
    if (
        any(len(sig) != 64 for sig in event_signatures)
        or len(event_signatures) != len(set(event_signatures))
    ):
        return {
            "version": VERSION,
            "project_id": project_id,
            "status": "BLOCKED_BEFORE_TRANSACTION_PREFLIGHT",
            "blockers": ["event_signature_integrity_failed"],
            "ready_for_probe": False,
            "ready_for_real_write": False,
            "real_write_performed": False,
        }

    execution_bundle = {
        "version": VERSION,
        "project_id": project_id,
        "projection_version": PROJECTION_VERSION,
        "contract_version": CONTRACT_VERSION,
        "events": event_plans,
    }
    execution_signature = _execution_signature(project_id, event_plans)

    return {
        "version": VERSION,
        "project_id": project_id,
        "status": "READY_FOR_ROLLBACK_ONLY_PROBE",
        "blockers": [],
        "projection_version": PROJECTION_VERSION,
        "contract_version": CONTRACT_VERSION,
        "projected_event_count": len(event_plans),
        "projected_evidence_link_count": sum(
            len(row.get("evidence_links") or []) for row in event_plans
        ),
        "event_signatures": sorted(event_signatures),
        "review_fingerprint": execution_signature,
        "execution_signature": execution_signature,
        "confirmation_token": (
            f"WRITE_RESPONSE_TRUTH:{project_id}:{execution_signature[:12]}"
        ),
        "execution_bundle": execution_bundle,
        "ready_for_probe": True,
        "ready_for_real_write": False,
        "real_write_performed": False,
        "response_truth_changed": False,
        "human_review_created": False,
        "cutover_changed": False,
    }


def build_response_truth_transaction_preflight(
    client: Any,
    *,
    project_id: str,
) -> dict[str, Any]:
    projection = run_contract_verified_response_truth_projection_shadow(
        client,
        project_id=project_id,
    )
    return build_transaction_preflight_from_projection(
        project_id=project_id,
        projection=projection,
    )
