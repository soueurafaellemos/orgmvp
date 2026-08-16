from __future__ import annotations

"""NAVE V28.7.2A — Evidence-led Project Domain Reconciliation Kernel.

This layer runs after the V28.7.1D compatibility normalization. It does not promote
``domain_primary`` and it never auto-merges two existing Project Solution Instances.
"""

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Mapping, Sequence
from uuid import NAMESPACE_URL, uuid4, uuid5

from project_domain_identity import normalize_name, resolve_observed_identity
from project_semantic_observations import (
    collect_project_context_and_constraints,
    collect_project_semantic_observations,
)

RECONCILIATION_VERSION = "V28.7.2A"
RECONCILIATION_SCHEMA_VERSION = "28.7.2a"
RECONCILIATION_RPC = "apply_project_domain_reconciliation_v2872a"


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, Mapping):
        return [dict(data)]
    return [dict(row) for row in (data or []) if isinstance(row, Mapping)]


def _read_rows(client: Any, table: str, *, equals: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    query = client.table(table).select("*")
    for key, value in (equals or {}).items():
        query = query.eq(key, value)
    return _rows(query.execute())


def _stable_uuid(label: str) -> str:
    return str(uuid5(NAMESPACE_URL, label))


def _sha(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _project_entity(client: Any, project_id: str) -> dict[str, Any] | None:
    rows = _rows(client.table("knowledge_entities").select("*").eq("domain_table", "projects").eq("domain_id", project_id).limit(1).execute())
    return rows[0] if rows else None


def probe_reconciliation_schema(client: Any) -> dict[str, Any]:
    try:
        for table in ("semantic_observations", "project_context_elements", "project_requirement_constraints"):
            client.table(table).select("id").limit(1).execute()
        client.table("project_domain_reconciliation_status").select("project_id").limit(1).execute()
        return {"available": True, "status": "ready"}
    except Exception as exc:
        text = str(exc)
        missing = "PGRST205" in text or "does not exist" in text.lower() or "schema cache" in text.lower()
        return {"available": False, "status": "schema_missing" if missing else "schema_check_error", "error": text}


def _group_solution_observations(observations: Sequence[Mapping[str, Any]]) -> list[list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for raw in observations:
        if raw.get("observation_kind") not in {"solution_candidate", "solution_mention"}:
            continue
        key = normalize_name(raw.get("observed_name"))
        if key:
            grouped.setdefault(key, []).append(dict(raw))
    return list(grouped.values())


def build_reconciliation_plan(
    project_id: str,
    observations: Sequence[Mapping[str, Any]],
    existing_solutions: Sequence[Mapping[str, Any]],
    current_outcomes: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Pure planning step used by runtime and tests."""
    solutions = [dict(row) for row in existing_solutions]
    current_state = {
        (str(row.get("entity_id") or ""), str(row.get("outcome_type") or "")): str(row.get("outcome_status") or "")
        for row in current_outcomes
        if row.get("entity_id") and row.get("outcome_type")
    }
    solution_mutations: list[dict[str, Any]] = []
    occurrences: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []
    observation_resolutions: list[dict[str, Any]] = []
    evidence_links: list[dict[str, Any]] = []

    for raw in observations:
        if raw.get("observation_kind") == "material_mention":
            observation_resolutions.append({
                "id": raw["id"], "status": "no_domain_object", "resolution_action": "no_domain_object",
                "resolved_entity_id": None, "resolved_domain_table": None, "resolved_domain_id": None,
                "resolution_detail": {"reason": "post_event_material_is_not_automatically_solution"},
            })

    for group in _group_solution_observations(observations):
        primary = next((row for row in group if row.get("occurrence_phase") == "execution"), group[0])
        name = str(primary.get("observed_name") or "").strip()
        resolution = resolve_observed_identity(name, solutions)
        action = resolution.get("action")

        if action == "review_required":
            candidates = [str(row.get("id")) for row in resolution.get("candidates") or [] if row.get("id")]
            for obs in group:
                observation_resolutions.append({
                    "id": obs["id"], "status": "review_required", "resolution_action": "review_required",
                    "resolved_entity_id": None, "resolved_domain_table": None, "resolved_domain_id": None,
                    "resolution_detail": {"reason": resolution.get("reason"), "candidate_solution_ids": candidates, "score": resolution.get("score")},
                })
            continue

        if action == "attach_existing":
            target = dict(resolution["target"])
        else:
            qualified_create = any(
                (
                    row.get("occurrence_role") == "proposal"
                    and float(row.get("model_confidence") or 0.0) >= 0.90
                    and float(row.get("source_authority_score") or 0.0) >= 0.80
                )
                or (
                    row.get("observation_kind") == "solution_candidate"
                    and row.get("occurrence_phase") == "execution"
                    and str(row.get("observed_status") or "") in {"executed", "partial", "not_executed", "planned"}
                    and float(row.get("model_confidence") or 0.0) >= 0.90
                )
                for row in group
            )
            if not qualified_create:
                for obs in group:
                    observation_resolutions.append({
                        "id": obs["id"], "status": "open",
                        "resolution_action": "insufficient_evidence",
                        "resolved_entity_id": None, "resolved_domain_table": None, "resolved_domain_id": None,
                        "resolution_detail": {
                            "reason": "new_solution_requires_proposal_or_explicit_execution_evidence",
                            "identity_reason": resolution.get("reason"),
                            "score": resolution.get("score"),
                        },
                    })
                continue
            identity_key = "evidence:" + normalize_name(name).replace(" ", "-")[:180]
            domain_id = _stable_uuid(f"nave:v2872a:solution:{project_id}:{identity_key}")
            entity_id = _stable_uuid(f"nave:v2872a:solution-entity:{project_id}:{identity_key}")
            target = {
                "id": domain_id,
                "entity_id": entity_id,
                "identity_key": identity_key,
                "solution_kind": str(primary.get("observed_type") or "activation"),
                "name": name,
                "description": None,
                "journey_stage": None,
                "roles": ["activation"] if str(primary.get("observed_type") or "") == "activation" else [],
                "confidence": max(float(row.get("model_confidence") or 0.0) for row in group),
                "source_authority_score": max(float(row.get("source_authority_score") or 0.0) for row in group),
                "attributes": {
                    "normalized_by": RECONCILIATION_VERSION,
                    "origin": "evidence_led_v2872a",
                    "observation_ids": [str(row.get("id")) for row in group],
                },
            }
            solution_mutations.append(target)
            solutions.append(target)

        proposal_observation = max(
            (row for row in group if row.get("occurrence_role") == "proposal"),
            key=lambda row: (float(row.get("source_authority_score") or 0.0), float(row.get("model_confidence") or 0.0)),
            default=None,
        )

        for obs in group:
            observation_resolutions.append({
                "id": obs["id"], "status": "reconciled",
                "resolution_action": "create_instance" if action == "create_new" else "attach_occurrence",
                "resolved_entity_id": target.get("entity_id"),
                "resolved_domain_table": "project_solution_instances",
                "resolved_domain_id": target.get("id"),
                "resolution_detail": {"reason": resolution.get("reason"), "score": resolution.get("score")},
            })
            occurrence_id = _stable_uuid(
                f"nave:v2872a:occurrence:{target.get('id')}:{obs.get('evidence_unit_id')}:{obs.get('occurrence_phase')}:{obs.get('occurrence_role')}"
            )
            occurrences.append({
                "id": occurrence_id,
                "solution_instance_id": target.get("id"),
                "source_asset_id": obs.get("source_asset_id"),
                "evidence_unit_id": obs.get("evidence_unit_id"),
                "occurrence_phase": obs.get("occurrence_phase") or "reference",
                "occurrence_role": obs.get("occurrence_role") or "reference",
                "observed_name": obs.get("observed_name"),
                "observed_status": obs.get("observed_status"),
                "section_key": None,
                "source_page": None,
                "source_locator": {},
                "confidence": obs.get("model_confidence"),
                "attributes": {"semantic_observation_id": obs.get("id"), "origin": "evidence_led_v2872a"},
            })
            evidence_links.append({
                "project_id": project_id,
                "object_entity_id": target.get("entity_id"),
                "domain_table": "project_solution_instances",
                "domain_id": target.get("id"),
                "evidence_unit_id": obs.get("evidence_unit_id"),
                "link_role": "occurrence",
                "context": {"semantic_observation_id": obs.get("id"), "phase": obs.get("occurrence_phase"), "role": obs.get("occurrence_role")},
                "binding_confidence": obs.get("model_confidence"),
            })
            execution_status = str(obs.get("observed_status") or "").strip()
            if execution_status in {"executed", "partial", "not_executed", "planned"}:
                outcome_id = _stable_uuid(f"nave:v2872a:execution-outcome:{obs.get('id')}:{target.get('entity_id')}:{execution_status}")
                outcomes.append({
                    "id": outcome_id,
                    "entity_id": target.get("entity_id"),
                    "outcome_type": "execution_status",
                    "outcome_status": execution_status,
                    "outcome_at": None,
                    "reason": f"Execution result '{execution_status}' observed as '{obs.get('observed_name')}'.",
                    "source_evidence_id": obs.get("evidence_unit_id"),
                    "source_observation_id": obs.get("id"),
                    "confidence": obs.get("model_confidence"),
                    "authority_score": obs.get("source_authority_score"),
                    "attributes": {"normalized_by": RECONCILIATION_VERSION, "semantic_observation_id": obs.get("id")},
                })

        # A proposal occurrence can also establish proposal_status, but state is
        # materialized only once per identity/group even when several proposal
        # Evidence Units mention the same solution.
        if (
            proposal_observation is not None
            and float(proposal_observation.get("model_confidence") or 0.0) >= 0.90
            and float(proposal_observation.get("source_authority_score") or 0.0) >= 0.80
            and not current_state.get((str(target.get("entity_id") or ""), "proposal_status"))
        ):
            proposal_outcome_id = _stable_uuid(
                f"nave:v2872a:proposal-outcome:{proposal_observation.get('id')}:{target.get('entity_id')}"
            )
            outcomes.append({
                "id": proposal_outcome_id,
                "entity_id": target.get("entity_id"),
                "outcome_type": "proposal_status",
                "outcome_status": "proposed",
                "outcome_at": None,
                "reason": f"Proposal occurrence observed as '{proposal_observation.get('observed_name')}'.",
                "source_evidence_id": proposal_observation.get("evidence_unit_id"),
                "source_observation_id": proposal_observation.get("id"),
                "confidence": proposal_observation.get("model_confidence"),
                "authority_score": proposal_observation.get("source_authority_score"),
                "attributes": {
                    "normalized_by": RECONCILIATION_VERSION,
                    "semantic_observation_id": proposal_observation.get("id"),
                    "evidence_led_state": True,
                },
            })

    # Deduplicate deterministic occurrence/outcome/link identities in memory.
    occurrences = list({row["id"]: row for row in occurrences}.values())
    outcomes = list({row["id"]: row for row in outcomes}.values())
    evidence_links = list({
        _sha((row.get("object_entity_id"), row.get("evidence_unit_id"), row.get("link_role"), row.get("context"))): row
        for row in evidence_links
    }.values())
    return {
        "solutions": solution_mutations,
        "occurrences": occurrences,
        "outcomes": outcomes,
        "observation_resolutions": observation_resolutions,
        "evidence_links": evidence_links,
    }


def _start_run(client: Any, project_id: str, project_entity_id: str, signature: Any) -> str:
    run_id = str(uuid4())
    payload = {
        "id": run_id,
        "analyzer_type": "project_domain_reconciliation",
        "scope_kind": "project",
        "scope_entity_id": project_entity_id,
        "pipeline_version": RECONCILIATION_VERSION,
        "code_version": RECONCILIATION_VERSION,
        "schema_version": RECONCILIATION_SCHEMA_VERSION,
        "input_signature": _sha(signature),
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {"project_id": project_id, "legacy_shadow": True, "auto_merge_existing_identities": False},
    }
    rows = _rows(client.table("intelligence_runs").insert(payload).execute())
    if not rows:
        raise RuntimeError("Supabase não confirmou intelligence_run de reconciliation")
    return str(rows[0].get("id") or run_id)


def _mark_run_error(client: Any, run_id: str, exc: Exception) -> None:
    try:
        client.table("intelligence_runs").update({
            "status": "error", "completed_at": datetime.now(timezone.utc).isoformat(),
            "error_code": "domain_reconciliation_error", "error_detail": str(exc)[:4000],
        }).eq("id", run_id).execute()
    except Exception:
        pass


def fetch_project_reconciliation_status(client: Any, project_id: str) -> dict[str, Any]:
    rows = _rows(client.table("project_domain_reconciliation_status").select("*").eq("project_id", project_id).limit(1).execute())
    return rows[0] if rows else {"project_id": project_id}


def reconcile_project_domain(client: Any, project_id: str) -> dict[str, Any]:
    probe = probe_reconciliation_schema(client)
    if not probe.get("available"):
        return {"project_id": project_id, "status": probe.get("status"), "warnings": [probe.get("error")]}

    project_entity = _project_entity(client, project_id)
    if not project_entity:
        return {"project_id": project_id, "status": "blocked", "warnings": ["Project knowledge_entity mirror ausente; rode Domain Truth Gate primeiro."]}

    observation_result = collect_project_semantic_observations(client, project_id)
    context_result = collect_project_context_and_constraints(client, project_id)
    observations = observation_result.get("observations") or []
    existing_solutions = _read_rows(client, "project_solution_instances", equals={"project_id": project_id})
    current_outcomes = _read_rows(client, "entity_current_outcomes", equals={"project_id": project_id})
    plan = build_reconciliation_plan(project_id, observations, existing_solutions, current_outcomes)

    bundle = {
        "version": RECONCILIATION_VERSION,
        "project_entity_id": str(project_entity.get("id")),
        "observations": observations,
        **plan,
        **context_result,
    }
    run_id = _start_run(client, project_id, str(project_entity.get("id")), {
        "observations": [(o.get("observation_hash"), o.get("observed_name")) for o in observations],
        "existing_solutions": [(s.get("id"), s.get("name")) for s in existing_solutions],
        "current_outcomes": [(o.get("entity_id"), o.get("outcome_type"), o.get("outcome_status")) for o in current_outcomes],
        "context": context_result,
    })
    try:
        response = client.rpc(RECONCILIATION_RPC, {
            "p_project_id": project_id,
            "p_run_id": run_id,
            "p_bundle": bundle,
        }).execute()
        rpc_rows = _rows(response)
        rpc_result = rpc_rows[0] if rpc_rows else {}
        status = fetch_project_reconciliation_status(client, project_id)
        observation_by_id = {str(row.get("id")): row for row in observations if row.get("id")}
        review_names = list(dict.fromkeys(
            str((observation_by_id.get(str(r.get("id"))) or {}).get("observed_name") or "").strip()
            for r in (plan.get("observation_resolutions") or [])
            if r.get("status") == "review_required"
            and str((observation_by_id.get(str(r.get("id"))) or {}).get("observed_name") or "").strip()
        ))
        no_domain_names = list(dict.fromkeys(
            str((observation_by_id.get(str(r.get("id"))) or {}).get("observed_name") or "").strip()
            for r in (plan.get("observation_resolutions") or [])
            if r.get("status") == "no_domain_object"
            and str((observation_by_id.get(str(r.get("id"))) or {}).get("observed_name") or "").strip()
        ))
        execution_names = list(dict.fromkeys(
            str(row.get("observed_name") or "").strip()
            for row in observations
            if str(row.get("observed_status") or "") in {"executed", "partial", "not_executed", "planned"}
            and str(row.get("observed_name") or "").strip()
        ))
        return {
            "project_id": project_id,
            "status": "completed",
            "run_id": run_id,
            "rpc": rpc_result,
            "reconciliation": status,
            "actions": {
                "observations": len(observations),
                "new_solutions": len(plan.get("solutions") or []),
                "new_solution_names": [str(row.get("name")) for row in (plan.get("solutions") or []) if row.get("name")],
                "occurrences": len(plan.get("occurrences") or []),
                "outcomes": len(plan.get("outcomes") or []),
                "execution_outcomes": sum(1 for row in (plan.get("outcomes") or []) if row.get("outcome_type") == "execution_status"),
                "proposal_outcomes": sum(1 for row in (plan.get("outcomes") or []) if row.get("outcome_type") == "proposal_status"),
                "execution_names": execution_names,
                "review_required": sum(1 for r in plan.get("observation_resolutions") or [] if r.get("status") == "review_required"),
                "review_names": review_names,
                "no_domain_object": sum(1 for r in plan.get("observation_resolutions") or [] if r.get("status") == "no_domain_object"),
                "no_domain_names": no_domain_names,
                "context_elements": len(context_result.get("context_elements") or []),
                "requirement_constraints": len(context_result.get("requirement_constraints") or []),
            },
            "warnings": [],
        }
    except Exception as exc:
        _mark_run_error(client, run_id, exc)
        return {"project_id": project_id, "status": "transaction_error", "run_id": run_id, "warnings": [str(exc)]}
