from __future__ import annotations

"""NAVE V28.7.3B2.15.3.1 — Frozen Golden Transaction Preflight.

Performance hotfix for B2.15.3.

The original B2.15.3 preflight rebuilt B2.12.2.2 -> B2.14 -> B2.15.2.1 live on every
button click. That is unnecessary after both B2.15.2.1 Golden projections were reviewed
and frozen, and it makes JOVI especially slow.

B2.15.3.1 instead loads the SHA-256 locked Golden projection artifact and performs only
small live guard queries against the current database before preparing the transaction.
No governance gate is relaxed.
"""

from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
import json

VERSION = "V28.7.3B2.15.3.1"
WRITER_VERSION = "V28.7.3B2.15.3"
PROJECTION_VERSION = "V28.7.3B2.15.2.1"
CONTRACT_VERSION = "V28.7.3B2.7.1"
RPC_PROBE = "diagnose_contract_verified_response_truth_b2153"

CHAMBINHO = "0d9f1608-4bf7-4fd0-81ab-f303fdb0c136"
JOVI = "01415104-72f2-4b8e-aeca-2dd24c231a7d"

BASELINE_DIR = Path(__file__).resolve().parent / "baselines"
BASELINES = {
    CHAMBINHO: {
        "filename": "NAVE_B2_15_2_1_RESPONSE_TRUTH_PROJECTION_0d9f1608-4bf7-4fd0-81ab-f303fdb0c136.json",
        "sha256": "424a9c0a7992c99a7a37117784d7304ecb86033431e40d8687171a20286264d2",
        "expected_current": 13,
        "expected_events": 3,
        "expected_evidence_links": 3,
    },
    JOVI: {
        "filename": "NAVE_B2_15_2_1_RESPONSE_TRUTH_PROJECTION_01415104-72f2-4b8e-aeca-2dd24c231a7d.json",
        "sha256": "e1c5b18c9faecbf15e63d34fc5c482a5927130b5fb18f1f07d4c8f60778ade44",
        "expected_current": 69,
        "expected_events": 0,
        "expected_evidence_links": 0,
    },
}


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, Mapping):
        return [dict(data)]
    return [dict(row) for row in (data or []) if isinstance(row, Mapping)]


def _load_locked_projection(project_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    spec = BASELINES.get(str(project_id or ""))
    if spec is None:
        raise ValueError(f"B2.15.3.1 unsupported Golden project: {project_id}")

    path = BASELINE_DIR / spec["filename"]
    raw = path.read_bytes()
    actual_sha256 = sha256(raw).hexdigest()
    if actual_sha256 != spec["sha256"]:
        raise RuntimeError(
            "B2.15.3.1 frozen Golden projection hash mismatch: "
            f"expected {spec['sha256']}, got {actual_sha256}"
        )
    projection = json.loads(raw.decode("utf-8"))
    return projection, {**spec, "actual_sha256": actual_sha256}


def _execution_signature(project_id: str, event_plans: list[Mapping[str, Any]]) -> str:
    signatures = sorted(str(row.get("event_signature") or "") for row in event_plans)
    return sha256(
        f"{WRITER_VERSION}|{project_id}|{','.join(signatures)}".encode("utf-8")
    ).hexdigest()


def _lightweight_live_guards(
    client: Any,
    *,
    project_id: str,
    projection: Mapping[str, Any],
    baseline_spec: Mapping[str, Any],
) -> dict[str, Any]:
    project_id = str(project_id or "")
    event_plans = [
        dict(row)
        for row in (projection.get("event_plans") or [])
        if isinstance(row, Mapping)
    ]

    status_rows = _rows(
        client.table("project_requirement_response_truth_status")
        .select("requirement_id,project_id,requirement_entity_id,response_truth_status")
        .eq("project_id", project_id)
        .execute()
    )

    event_probe = _rows(
        client.table("project_requirement_response_truth_events")
        .select("id")
        .limit(1)
        .execute()
    )
    evidence_probe = _rows(
        client.table("project_requirement_response_truth_evidence")
        .select("event_id")
        .limit(1)
        .execute()
    )
    current_truth_probe = _rows(
        client.table("project_requirement_response_current_truth")
        .select("response_truth_event_id")
        .limit(1)
        .execute()
    )
    cutover_rows = _rows(
        client.table("project_domain_cutover_readiness")
        .select("project_id,domain_key,read_mode")
        .eq("project_id", project_id)
        .eq("domain_key", "requirements")
        .execute()
    )

    target_identity_checks = []
    evidence_checks = []
    for event in event_plans:
        rid = str(event.get("requirement_id") or "")
        entity_id = str(event.get("requirement_entity_id") or "")
        requirement_rows = _rows(
            client.table("project_requirement_truth_status")
            .select("id,project_id,entity_id,truth_state,lifecycle_status")
            .eq("id", rid)
            .eq("project_id", project_id)
            .limit(2)
            .execute()
        )
        target_identity_checks.append({
            "requirement_id": rid,
            "requirement_entity_id": entity_id,
            "row_count": len(requirement_rows),
            "pass": (
                len(requirement_rows) == 1
                and str(requirement_rows[0].get("entity_id") or "") == entity_id
                and str(requirement_rows[0].get("lifecycle_status") or "") == "active"
                and str(requirement_rows[0].get("truth_state") or "")
                    in {"verified", "human_confirmed"}
            ),
        })

        for link in event.get("evidence_links") or []:
            if not isinstance(link, Mapping):
                continue
            eid = str(link.get("evidence_unit_id") or "")
            evidence_rows = _rows(
                client.table("evidence_units")
                .select("id")
                .eq("id", eid)
                .limit(2)
                .execute()
            )
            evidence_checks.append({
                "evidence_unit_id": eid,
                "row_count": len(evidence_rows),
                "pass": len(evidence_rows) == 1,
            })

    checks = {
        "frozen_projection_status_pass": (
            projection.get("status") == "PASS_CONTRACT_VERIFIED_RESPONSE_TRUTH_PROJECTION"
            and projection.get("all_checks_pass") is True
            and projection.get("failed_checks") == []
        ),
        "frozen_projection_version_exact": (
            str(projection.get("version") or "") == PROJECTION_VERSION
        ),
        "frozen_projection_project_exact": (
            str(projection.get("project_id") or "") == project_id
        ),
        "frozen_projection_current_count_exact": (
            int(projection.get("current_requirement_count") or 0)
            == int(baseline_spec["expected_current"])
        ),
        "frozen_projection_event_count_exact": (
            int(projection.get("projected_event_count") or 0)
            == int(baseline_spec["expected_events"])
            == len(event_plans)
        ),
        "frozen_projection_evidence_link_count_exact": (
            int(projection.get("projected_evidence_link_count") or 0)
            == int(baseline_spec["expected_evidence_links"])
        ),
        "live_current_status_count_matches_golden": (
            len(status_rows) == int(baseline_spec["expected_current"])
        ),
        "live_all_current_status_has_no_persisted_truth": (
            len(status_rows) == int(baseline_spec["expected_current"])
            and all(
                str(row.get("response_truth_status") or "")
                == "no_persisted_response_truth"
                for row in status_rows
            )
        ),
        "live_event_ledger_empty": len(event_probe) == 0,
        "live_evidence_ledger_empty": len(evidence_probe) == 0,
        "live_current_response_truth_empty": len(current_truth_probe) == 0,
        "live_requirements_still_shadow_compare": (
            len(cutover_rows) == 1
            and str(cutover_rows[0].get("read_mode") or "") == "shadow_compare"
        ),
        "live_target_requirement_identity_exact": all(
            row["pass"] for row in target_identity_checks
        ),
        "live_target_evidence_units_exist": all(
            row["pass"] for row in evidence_checks
        ),
    }

    failed = [key for key, value in checks.items() if not value]
    return {
        "checks": checks,
        "failed_checks": failed,
        "all_checks_pass": not failed,
        "live_current_status_count": len(status_rows),
        "event_ledger_probe_count": len(event_probe),
        "evidence_ledger_probe_count": len(evidence_probe),
        "current_response_truth_probe_count": len(current_truth_probe),
        "target_identity_checks": target_identity_checks,
        "evidence_unit_checks": evidence_checks,
        "cutover_rows": cutover_rows,
    }


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
            "writer_version": WRITER_VERSION,
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
            "writer_version": WRITER_VERSION,
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

    event_signatures = [str(row.get("event_signature") or "") for row in event_plans]
    if (
        any(len(sig) != 64 for sig in event_signatures)
        or len(event_signatures) != len(set(event_signatures))
    ):
        return {
            "version": VERSION,
            "writer_version": WRITER_VERSION,
            "project_id": project_id,
            "status": "BLOCKED_BEFORE_TRANSACTION_PREFLIGHT",
            "blockers": ["event_signature_integrity_failed"],
            "ready_for_probe": False,
            "ready_for_real_write": False,
            "real_write_performed": False,
        }

    execution_bundle = {
        "version": WRITER_VERSION,
        "project_id": project_id,
        "projection_version": PROJECTION_VERSION,
        "contract_version": CONTRACT_VERSION,
        "events": event_plans,
    }
    execution_signature = _execution_signature(project_id, event_plans)

    return {
        "version": VERSION,
        "writer_version": WRITER_VERSION,
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
    projection, baseline_spec = _load_locked_projection(project_id)
    live = _lightweight_live_guards(
        client,
        project_id=project_id,
        projection=projection,
        baseline_spec=baseline_spec,
    )

    if not live["all_checks_pass"]:
        return {
            "version": VERSION,
            "writer_version": WRITER_VERSION,
            "project_id": project_id,
            "status": "BLOCKED_LIVE_GOLDEN_GUARD",
            "blockers": list(live["failed_checks"]),
            "baseline_sha256": baseline_spec["actual_sha256"],
            "live_guards": live,
            "ready_for_probe": False,
            "ready_for_real_write": False,
            "real_write_performed": False,
            "safe_to_write_response_truth": False,
        }

    result = build_transaction_preflight_from_projection(
        project_id=project_id,
        projection=projection,
    )
    result["baseline_sha256"] = baseline_spec["actual_sha256"]
    result["baseline_file"] = baseline_spec["filename"]
    result["projection_source"] = "sha256_locked_b21521_golden_artifact"
    result["live_guards"] = live
    result["safe_to_write_response_truth"] = False
    return result
