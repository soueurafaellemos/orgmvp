from __future__ import annotations

"""NAVE V28.7.2C0.2.4H3.1 — Requirement Reconciliation entrypoint.

This module preserves the installed C0.2.4/H1 SQL contract and H3 planner while using
H3.1's corrected cross-Evidence-Unit structural classification before persistence.
No auto-merge, delete, domain_primary promotion or Graph V28.6 rebuild is introduced.
"""

from datetime import datetime, timezone
import json
from typing import Any
from uuid import uuid4

import project_requirement_reconciliation as h3r
from project_requirement_semantic_h31 import (
    H31_VERSION,
    collect_project_requirement_observations_h31,
)

C0_VERSION = H31_VERSION
C0_SCHEMA_VERSION = h3r.C0_SCHEMA_VERSION
C0_RPC = h3r.C0_RPC


def _patch_plan_provenance(plan: dict[str, Any]) -> dict[str, Any]:
    """Ensure all newly materialized H3.1 objects say H3.1, not the H3 base module."""
    for row in plan.get("requirements") or []:
        attrs = dict(row.get("attributes") or {})
        attrs["normalized_by"] = H31_VERSION
        row["attributes"] = attrs

    for row in plan.get("occurrences") or []:
        attrs = dict(row.get("attributes") or {})
        attrs["normalized_by"] = H31_VERSION
        row["attributes"] = attrs

    for row in plan.get("evidence_links") or []:
        context = dict(row.get("context") or {})
        context["normalized_by"] = H31_VERSION
        row["context"] = context
        row["context_sha256"] = h3r._sha(context)
    return plan


def _start_run(client: Any, project_id: str, project_entity_id: str, signature: Any) -> str:
    run_id = str(uuid4())
    payload = {
        "id": run_id,
        "analyzer_type": "project_requirement_reconciliation",
        "scope_kind": "project",
        "scope_entity_id": project_entity_id,
        "pipeline_version": H31_VERSION,
        "code_version": H31_VERSION,
        "schema_version": C0_SCHEMA_VERSION,
        "input_signature": h3r._sha(signature),
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "project_id": project_id,
            "legacy_shadow": True,
            "auto_merge_existing_requirements": False,
            "cross_unit_structural_context": True,
            "golden_verifier_normalization_required": True,
        },
    }
    rows = h3r._rows(client.table("intelligence_runs").insert(payload).execute())
    if not rows:
        raise RuntimeError("Supabase não confirmou intelligence_run de Requirement Reconciliation H3.1")
    return str(rows[0].get("id") or run_id)


def reconcile_project_requirements(client: Any, project_id: str) -> dict[str, Any]:
    probe = h3r.probe_requirement_reconciliation_schema(client)
    if not probe.get("available"):
        return {
            "project_id": project_id,
            "status": probe.get("status"),
            "warnings": [probe.get("error")],
        }

    project_entity = h3r._project_entity(client, project_id)
    if not project_entity:
        return {
            "project_id": project_id,
            "status": "blocked",
            "warnings": ["Project knowledge_entity mirror ausente."],
        }

    extraction = collect_project_requirement_observations_h31(client, project_id)
    observations = extraction.get("observations") or []
    existing = h3r._read_rows(
        client,
        "project_requirements",
        equals={"project_id": project_id},
    )

    if existing and not observations:
        return {
            "project_id": project_id,
            "status": "blocked_empty_requirement_observation_bundle",
            "warnings": [
                "H3.1 não encontrou Evidence-backed Requirement observations; estado anterior preservado."
            ],
            "diagnostics": extraction.get("diagnostics") or [],
        }

    plan = h3r.build_requirement_reconciliation_plan(project_id, observations, existing)
    plan = _patch_plan_provenance(plan)
    bundle = {
        "version": H31_VERSION,
        "project_entity_id": str(project_entity.get("id")),
        "observations": observations,
        **plan,
    }

    run_id = _start_run(
        client,
        project_id,
        str(project_entity.get("id")),
        {
            "observations": [
                (row.get("observation_hash"), row.get("semantic_role"))
                for row in observations
            ],
            "existing_requirements": [
                (row.get("id"), row.get("title"), row.get("legacy_source_id"))
                for row in existing
            ],
        },
    )

    try:
        response = client.rpc(
            C0_RPC,
            {"p_project_id": project_id, "p_run_id": run_id, "p_bundle": bundle},
        ).execute()
        rpc_rows = h3r._rows(response)
        status = h3r.fetch_project_requirement_reconciliation_status(client, project_id)
        classified = {
            "scopes": [
                str(row.get("observed_name"))
                for row in observations
                if str(row.get("semantic_role")) in h3r.SCOPE_ROLES
            ],
            "attributes": [
                str(row.get("observed_name"))
                for row in observations
                if str(row.get("semantic_role")) in h3r.ATTRIBUTE_ROLES
            ],
            "contexts": [
                str(row.get("observed_name"))
                for row in observations
                if str(row.get("semantic_role")) in h3r.CONTEXT_ROLES
            ],
            "references": [
                str(row.get("observed_name"))
                for row in observations
                if str(row.get("semantic_role")) in h3r.REFERENCE_ROLES
            ],
            "suggestions": [
                str(row.get("observed_name"))
                for row in observations
                if str(row.get("semantic_role")) == "suggestion_signal"
            ],
            "examples": [
                str(row.get("observed_name"))
                for row in observations
                if str(row.get("semantic_role")) == "example_signal"
            ],
            "parameters": [
                str(row.get("observed_name"))
                for row in observations
                if str(row.get("semantic_role")) == "parameter_signal"
            ],
            "constraint_qualifiers": [
                str(row.get("observed_name"))
                for row in observations
                if str(row.get("semantic_role")) == "constraint_qualifier"
            ],
            "evidence_first": [
                str(row.get("observed_name"))
                for row in observations
                if str((row.get("attributes") or {}).get("origin_route")) == "evidence_first"
            ],
            "blocked_legacy_identity_ids": list(plan.get("blocked_existing_ids") or []),
            "h31_cross_unit_structural_overrides": int(
                (extraction.get("summary") or {}).get("h31_cross_unit_structural_overrides") or 0
            ),
        }
        gate = h3r._semantic_gate(status)
        return {
            "project_id": project_id,
            "version": H31_VERSION,
            "status": "completed" if gate["pass"] else "semantic_gate_blocked",
            "run_id": run_id,
            "rpc": rpc_rows[0] if rpc_rows else {},
            "requirement_reconciliation": status,
            "semantic_gate": gate,
            "actions": {
                "observations": len(observations),
                "new_requirements": len(plan.get("requirements") or []),
                "occurrences": len(plan.get("occurrences") or []),
                "review_required": sum(
                    1
                    for row in plan.get("observation_resolutions") or []
                    if row.get("status") == "review_required"
                ),
                "no_domain_object": sum(
                    1
                    for row in plan.get("observation_resolutions") or []
                    if row.get("status") == "no_domain_object"
                ),
                "semantic_gate_blockers": gate["blockers"],
                "new_requirement_titles": [
                    str(row.get("title")) for row in plan.get("requirements") or []
                ],
                **classified,
            },
            "diagnostics": extraction.get("diagnostics") or [],
            "extraction_summary": extraction.get("summary") or {},
            "warnings": []
            if gate["pass"]
            else [
                "Requirement Semantic Gate H3.1 bloqueou V28.7.2B: "
                + json.dumps(gate["components"], ensure_ascii=False, sort_keys=True)
            ],
        }
    except Exception as exc:
        h3r._mark_run_error(client, run_id, exc)
        return {
            "project_id": project_id,
            "status": "transaction_error",
            "run_id": run_id,
            "warnings": [str(exc)],
        }
