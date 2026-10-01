from __future__ import annotations

"""NAVE V28.7.3B2.12.5.4 — governed transactional Requirement identity supersession."""

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Mapping
from uuid import uuid4

from project_domain_reader import get_cutover_state
from project_intelligence_pipeline import requirement_reconciliation_contract
from project_requirement_identity_supersession_dry_run import run_hardened_dry_run

VERSION = "V28.7.3B2.12.5.4"
DRY_RUN_VERSION = "V28.7.3B2.12.4.1"
PROMOTION_VERSION = "V28.7.2C0.2.4H3.1.3P1"
RPC = "apply_project_requirement_identity_supersession_b2125"


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, Mapping):
        return [dict(data)]
    return [
        dict(row)
        for row in (data or [])
        if isinstance(row, Mapping)
    ]


def _sha(payload: Any) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_supersession_preflight(
    client: Any,
    *,
    project_id: str,
) -> dict[str, Any]:
    state = get_cutover_state(client, project_id, "requirements")
    contract = requirement_reconciliation_contract()
    dry = run_hardened_dry_run(client, project_id=project_id)
    dry_dict = dry.to_dict()

    blockers: list[str] = []
    if str(state.get("read_mode") or "") != "shadow_compare":
        blockers.append("requirements_not_shadow_compare")
    if not bool(contract.get("normal_pipeline_uses_h31")):
        blockers.append("normal_pipeline_not_h31")
    if str(contract.get("promotion_version") or "") != PROMOTION_VERSION:
        blockers.append("pipeline_promotion_version_mismatch")
    if dry.blocked_count:
        blockers.append("dry_run_blocked")

    if not dry.plans:
        status = "NO_TRANSACTION_REQUIRED" if not blockers else "BLOCKED"
        return {
            "version": VERSION,
            "project_id": project_id,
            "status": status,
            "ready_for_write": False,
            "blockers": blockers,
            "pipeline_contract": contract,
            "dry_run_report": dry_dict,
            "write_performed": False,
        }

    if len(dry.plans) != 1 or dry.ready_count != 1:
        blockers.append("requires_exactly_one_ready_plan")

    plan = dry.plans[0]
    if plan.blockers:
        blockers.append("plan_contains_blockers")
    if plan.compatibility_status_after != "PASS_DATA_BRIDGE":
        blockers.append("projected_b2_1_not_pass")
    if plan.projected_collisions_after != 0:
        blockers.append("projected_collision_not_zero")

    execution_plan = deepcopy(plan.to_dict())

    patched_evidence: list[dict[str, Any]] = []
    for raw in execution_plan.get("evidence_actions") or []:
        action = dict(raw)
        if action.get("action") == "insert_single_survivor_evidence_link":
            context = {
                "identity_resolution": {
                    "version": VERSION,
                    "dry_run_version": DRY_RUN_VERSION,
                    "canonical_requirement_id": plan.survivor_requirement_id,
                    "superseded_requirement_ids": list(plan.superseded_requirement_ids),
                    "coalesced_source_evidence_link_ids": list(
                        action.get("coalesced_source_evidence_link_ids") or []
                    ),
                    "historical_source_links_preserved": True,
                }
            }
            action["context"] = context
            action["context_sha256"] = _sha(context)
        patched_evidence.append(action)
    execution_plan["evidence_actions"] = patched_evidence

    # Deterministic fingerprint of the exact reviewed transaction.
    # `generated_at` is intentionally excluded so a fresh preflight can be compared
    # with the user-reviewed plan without false drift.
    review_payload = {
        "version": VERSION,
        "project_id": project_id,
        "pipeline_promotion_version": PROMOTION_VERSION,
        "execution_plan": execution_plan,
        "current_before": plan.current_before,
        "projected_current_after": plan.projected_current_after,
        "projected_collisions_after": plan.projected_collisions_after,
    }
    review_fingerprint = _sha(review_payload)

    bundle = {
        "bundle_version": VERSION,
        "project_id": project_id,
        "pipeline_promotion_version": PROMOTION_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "review_fingerprint": review_fingerprint,
        "dry_run_report": dry_dict,
        "execution_plan": execution_plan,
    }
    signature = _sha(bundle)

    return {
        "version": VERSION,
        "project_id": project_id,
        "status": "READY_FOR_EXPLICIT_TRANSACTION" if not blockers else "BLOCKED",
        "ready_for_write": not blockers,
        "blockers": blockers,
        "pipeline_contract": contract,
        "dry_run_report": dry_dict,
        "execution_plan": execution_plan,
        "execution_bundle": bundle,
        "execution_signature": signature,
        "review_fingerprint": review_fingerprint,
        "confirmation_token": (
            f"SUPERSEDE:{project_id}:{review_fingerprint[:12]}"
        ),
        "write_performed": False,
    }


def execute_governed_supersession(
    client: Any,
    *,
    project_id: str,
    confirmation_token: str,
    reviewed_fingerprint: str,
) -> dict[str, Any]:
    # Always rebuild preflight immediately before the RPC. Never execute a stale UI plan.
    preflight = build_supersession_preflight(
        client,
        project_id=project_id,
    )
    if not preflight.get("ready_for_write"):
        raise RuntimeError(
            "B2.12.5.4 write blocked by fresh preflight: "
            + ", ".join(preflight.get("blockers") or [preflight.get("status") or "unknown"])
        )

    fresh_fingerprint = str(preflight.get("review_fingerprint") or "")
    if not reviewed_fingerprint or fresh_fingerprint != reviewed_fingerprint:
        raise RuntimeError(
            "B2.12.5.4 transaction plan changed since the reviewed preflight. "
            "No write was attempted. Run PRE-FLIGHT again and review the new plan."
        )

    expected_token = str(preflight.get("confirmation_token") or "")
    if confirmation_token != expected_token:
        raise RuntimeError("B2.12.5.4 explicit confirmation token mismatch")

    run_id = str(uuid4())
    response = client.rpc(
        RPC,
        {
            "p_project_id": project_id,
            "p_run_id": run_id,
            "p_confirmation_token": confirmation_token,
            "p_review_fingerprint": reviewed_fingerprint,
            "p_pipeline_promotion_version": PROMOTION_VERSION,
            "p_execution_bundle": preflight["execution_bundle"],
            "p_execution_signature": preflight["execution_signature"],
        },
    ).execute()
    rows = _rows(response)
    if not rows:
        raise RuntimeError("B2.12.5 RPC returned no result")

    result = rows[0]
    if str(result.get("status") or "") != "COMPLETED_TRANSACTIONAL_SUPERSESSION":
        raise RuntimeError(
            "B2.12.5 RPC did not confirm completed supersession: "
            + str(result.get("status"))
        )

    return {
        "version": VERSION,
        "project_id": project_id,
        "status": "COMPLETED_TRANSACTIONAL_SUPERSESSION",
        "run_id": result.get("run_id") or run_id,
        "rpc": result,
        "preflight_signature": preflight["execution_signature"],
        "requirement_truth_changed": True,
        "response_truth_changed": False,
        "human_review_created": False,
        "cutover_changed": False,
    }
