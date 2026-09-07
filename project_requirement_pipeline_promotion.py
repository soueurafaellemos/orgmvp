from __future__ import annotations

"""Read-only verification for H3.1.3 normal-pipeline promotion."""

from typing import Any, Mapping

from project_domain_reader import get_cutover_state
from project_intelligence_pipeline import (
    REQUIREMENT_PIPELINE_PROMOTION_VERSION,
    get_requirement_reconciliation_entrypoint,
    requirement_reconciliation_contract,
)
from project_requirement_reconciliation_h31 import (
    C0_VERSION as H31_RECONCILIATION_VERSION,
    reconcile_project_requirements as h31_reconcile_project_requirements,
)
from project_requirement_semantic_h31 import H31_VERSION


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, Mapping):
        return [dict(data)]
    return [
        dict(row)
        for row in (data or [])
        if isinstance(row, Mapping)
    ]


def verify_requirement_pipeline_promotion(
    client: Any,
    *,
    project_id: str,
) -> dict[str, Any]:
    contract = requirement_reconciliation_contract()
    selected = get_requirement_reconciliation_entrypoint()
    state = get_cutover_state(client, project_id, "requirements")

    latest = _rows(
        client.table("intelligence_runs")
        .select("*")
        .eq("analyzer_type", "project_requirement_reconciliation")
        .order("started_at", desc=True)
        .limit(20)
        .execute()
    )
    project_runs = [
        row
        for row in latest
        if str((row.get("metadata") or {}).get("project_id") or "") == str(project_id)
    ]
    latest_project_run = project_runs[0] if project_runs else None

    checks = {
        "entrypoint_object_is_h31": selected is h31_reconcile_project_requirements,
        "entrypoint_module_is_h31": selected.__module__ == "project_requirement_reconciliation_h31",
        "contract_normal_pipeline_uses_h31": bool(contract.get("normal_pipeline_uses_h31")),
        "contract_h31_version": str(contract.get("requirement_reconciliation_version") or "") == H31_VERSION,
        "reconciliation_module_version_matches_semantic_version": H31_RECONCILIATION_VERSION == H31_VERSION,
        "requirements_read_mode_still_shadow_compare": str(state.get("read_mode") or "") == "shadow_compare",
        "domain_primary_not_changed": contract.get("domain_primary_changed") is False,
        "canary_not_changed": contract.get("canary_changed") is False,
        "auto_merge_still_false": contract.get("auto_merge_existing_requirements") is False,
        "human_review_not_created": contract.get("human_review_created") is False,
        "promotion_does_not_trigger_pipeline_run": contract.get("pipeline_run_triggered_by_promotion") is False,
        "promotion_does_not_trigger_graph_rebuild": contract.get("graph_rebuild_triggered_by_promotion") is False,
    }
    failed = [key for key, value in checks.items() if not value]

    return {
        "version": REQUIREMENT_PIPELINE_PROMOTION_VERSION,
        "project_id": project_id,
        "status": "PASS_PIPELINE_PROMOTION_WIRING" if not failed else "BLOCKED_PIPELINE_PROMOTION_WIRING",
        "all_checks_pass": not failed,
        "failed_checks": failed,
        "checks": checks,
        "contract": contract,
        "requirements_cutover_state": {
            "read_mode": state.get("read_mode"),
            "readiness_state": state.get("readiness_state"),
        },
        "latest_requirement_reconciliation_run": (
            {
                "id": latest_project_run.get("id"),
                "pipeline_version": latest_project_run.get("pipeline_version"),
                "code_version": latest_project_run.get("code_version"),
                "status": latest_project_run.get("status"),
                "started_at": latest_project_run.get("started_at"),
            }
            if latest_project_run
            else None
        ),
        "writes_performed": False,
        "pipeline_run_performed": False,
        "a_rerun_performed": False,
        "b_rerun_performed": False,
        "graph_rerun_performed": False,
        "truth_changed": False,
        "cutover_changed": False,
    }
