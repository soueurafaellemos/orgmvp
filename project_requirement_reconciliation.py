from __future__ import annotations

"""NAVE V28.7.2C0.2.4H2 — Structural Role Boundary Hotfix.

Runs in legacy_shadow after Solution reconciliation/audits and before Core Semantic B.
It verifies or classifies Requirement knowledge without auto-merging two existing
Requirement identities.
"""

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Mapping, Sequence
from uuid import NAMESPACE_URL, uuid4, uuid5

from project_requirement_identity import normalize_requirement_text, resolve_requirement_identity
from project_requirement_semantic_extractor import collect_project_requirement_observations

C0_VERSION = "V28.7.2C0.2.4H2"
C0_SCHEMA_VERSION = "28.7.2c0.2.4"
C0_RPC = "apply_project_requirement_reconciliation_v2872c0"

SCOPE_ROLES = {"channel_scope", "platform_scope", "deliverable_scope"}
ATTRIBUTE_ROLES = {"product_attribute", "experience_attribute"}
CONTEXT_ROLES = {"audience_context", "strategy_context", "form_prompt"}
REFERENCE_ROLES = {"reference_signal", "solution_reference"}
ROLE_ONLY_NO_DOMAIN = {
    "suggestion_signal", "example_signal", "parameter_signal", "constraint_qualifier",
}
NO_DOMAIN_ROLES = SCOPE_ROLES | ATTRIBUTE_ROLES | CONTEXT_ROLES | REFERENCE_ROLES | ROLE_ONLY_NO_DOMAIN


def _no_domain_resolution_action(role: str) -> tuple[str, str]:
    if role in SCOPE_ROLES:
        return "attach_scope", "scope"
    if role in ATTRIBUTE_ROLES:
        return "attach_attribute", "attribute"
    if role in CONTEXT_ROLES:
        return "preserve_context", "context"
    if role in REFERENCE_ROLES:
        return "preserve_reference", "reference"
    if role == "suggestion_signal":
        return "preserve_suggestion", "suggestion"
    if role == "example_signal":
        return "preserve_example", "example"
    if role == "parameter_signal":
        return "attach_parameter", "parameter"
    if role == "constraint_qualifier":
        return "attach_constraint_qualifier", "constraint_qualifier"
    return "no_domain_object", role or "no_domain_object"


def _semantic_gate(status: Mapping[str, Any]) -> dict[str, Any]:
    components = {
        "observations_open": int(status.get("observations_open") or 0),
        "observations_review_required": int(status.get("observations_review_required") or 0),
        "unexplained_legacy_shadow": int(status.get("unexplained_legacy_shadow") or 0),
        "conflicted_identities": int(status.get("conflicted") or 0),
        "identity_review_required": int(status.get("review_required") or 0),
    }
    blockers = sum(components.values())
    return {"pass": blockers == 0, "blockers": blockers, "components": components}


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, Mapping):
        return [dict(data)]
    return [dict(row) for row in (data or []) if isinstance(row, Mapping)]


def _read_rows(client: Any, table: str, *, equals: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    q = client.table(table).select("*")
    for key, value in (equals or {}).items():
        q = q.eq(key, value)
    return _rows(q.execute())


def _stable_uuid(label: str) -> str:
    return str(uuid5(NAMESPACE_URL, label))


def _sha(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _project_entity(client: Any, project_id: str) -> dict[str, Any] | None:
    rows = _rows(client.table("knowledge_entities").select("*").eq("domain_table", "projects").eq("domain_id", project_id).limit(1).execute())
    return rows[0] if rows else None


def probe_requirement_reconciliation_schema(client: Any) -> dict[str, Any]:
    try:
        for table in ("project_requirement_occurrences", "project_requirement_truth_status", "project_requirement_reconciliation_status"):
            client.table(table).select("project_id").limit(1).execute()
        return {"available": True, "status": "ready"}
    except Exception as exc:
        text = str(exc)
        missing = "PGRST205" in text or "does not exist" in text.lower() or "schema cache" in text.lower()
        return {"available": False, "status": "schema_missing" if missing else "schema_check_error", "error": text}


def _new_requirement_from_observation(project_id: str, obs: Mapping[str, Any]) -> dict[str, Any]:
    normalized = normalize_requirement_text(obs.get("observed_name"))
    key = "evidence:" + normalized.replace(" ", "-")[:180]
    domain_id = _stable_uuid(f"nave:v2872c0_2:requirement:{project_id}:{key}")
    entity_id = _stable_uuid(f"nave:v2872c0_2:requirement-entity:{project_id}:{key}")
    return {
        "id": domain_id,
        "entity_id": entity_id,
        "requirement_type": str(obs.get("observed_type") or "other"),
        "title": str(obs.get("observed_name") or "Requisito").strip(),
        "normalized_name": normalized,
        "description": str((obs.get("attributes") or {}).get("evidence_text") or "")[:1200] or None,
        "priority": "not_informed",
        "mandatory": bool((obs.get("attributes") or {}).get("mandatory", True)),
        "status": "active",
        "confidence": float(obs.get("model_confidence") or 0.0),
        "source_authority_score": float(obs.get("source_authority_score") or 0.0),
        "attributes": {
            "normalized_by": C0_VERSION,
            "origin": "evidence_led_v2872c0_2",
            "source_observation_id": obs.get("id"),
        },
    }


def build_requirement_reconciliation_plan(
    project_id: str,
    observations: Sequence[Mapping[str, Any]],
    existing_requirements: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    requirements = [dict(row) for row in existing_requirements]
    new_requirements: list[dict[str, Any]] = []
    occurrences: list[dict[str, Any]] = []
    resolutions: list[dict[str, Any]] = []
    evidence_links: list[dict[str, Any]] = []

    # Pass 1: current Evidence classifies legacy recall identities before any Evidence-first
    # binding is attempted. A legacy identity classified as no-domain may remain preserved
    # for recall/history, but it is not eligible to absorb a current Requirement obligation.
    blocked_existing_ids: set[str] = set()
    for raw in observations:
        obs = dict(raw)
        attrs = obs.get("attributes") if isinstance(obs.get("attributes"), Mapping) else {}
        if str(attrs.get("origin_route") or "") != "legacy_recall":
            continue
        if str(obs.get("semantic_role") or "") not in NO_DOMAIN_ROLES:
            continue
        rid = str(attrs.get("requirement_id") or "")
        if rid:
            blocked_existing_ids.add(rid)

    for raw in observations:
        obs = dict(raw)
        semantic_role = str(obs.get("semantic_role") or "")
        attrs = obs.get("attributes") if isinstance(obs.get("attributes"), Mapping) else {}

        if semantic_role in NO_DOMAIN_ROLES:
            resolution_action, classification = _no_domain_resolution_action(semantic_role)
            resolutions.append({
                "id": obs["id"], "status": "no_domain_object", "resolution_action": resolution_action,
                "resolved_entity_id": None, "resolved_domain_table": None, "resolved_domain_id": None,
                "resolution_detail": {
                    "classification": classification,
                    "semantic_role": semantic_role,
                    "legacy_requirement_id": attrs.get("legacy_requirement_id"),
                    "requirement_id": attrs.get("requirement_id"),
                },
            })
            continue

        resolver_requirements = requirements
        if str(attrs.get("origin_route") or "") == "evidence_first" and blocked_existing_ids:
            resolver_requirements = [
                row for row in requirements if str(row.get("id") or "") not in blocked_existing_ids
            ]
        resolution = resolve_requirement_identity(obs, resolver_requirements)
        action = str(resolution.get("action") or "")
        if action == "review_required":
            resolutions.append({
                "id": obs["id"], "status": "review_required", "resolution_action": "review_required",
                "resolved_entity_id": None, "resolved_domain_table": None, "resolved_domain_id": None,
                "resolution_detail": {
                    "reason": resolution.get("reason"),
                    "candidate_requirement_ids": [str(row.get("id")) for row in resolution.get("candidates") or [] if row.get("id")],
                    "score": resolution.get("score"),
                },
            })
            continue

        if action == "attach_existing":
            target = dict(resolution["target"])
            resolution_action = "attach_requirement_occurrence"
        else:
            qualified = (
                semantic_role == "requirement_candidate"
                and float(obs.get("model_confidence") or 0.0) >= 0.92
                and float(obs.get("source_authority_score") or 0.0) >= 0.80
            )
            if not qualified:
                resolutions.append({
                    "id": obs["id"], "status": "open", "resolution_action": "insufficient_evidence",
                    "resolved_entity_id": None, "resolved_domain_table": None, "resolved_domain_id": None,
                    "resolution_detail": {"reason": "new_requirement_requires_explicit_high_authority_evidence"},
                })
                continue
            target = _new_requirement_from_observation(project_id, obs)
            new_requirements.append(target)
            requirements.append(target)
            resolution_action = "create_requirement"

        occurrence_role = "constraint" if semantic_role == "constraint_candidate" else "requirement"
        # Occurrence identity is Requirement + Evidence + semantic role. The observed
        # wording is intentionally excluded so legacy-recall and evidence-first routes
        # converge on one occurrence when they resolve to the same Requirement atom.
        occurrence_hash = _sha({
            "project": project_id,
            "requirement": target.get("id"),
            "evidence": obs.get("evidence_unit_id"),
            "role": occurrence_role,
        })
        occurrence_id = _stable_uuid("nave:v2872c0_2:requirement-occurrence:" + occurrence_hash)
        occurrences.append({
            "id": occurrence_id,
            "requirement_id": target.get("id"),
            "legacy_requirement_id": attrs.get("legacy_requirement_id"),
            "source_asset_id": obs.get("source_asset_id"),
            "evidence_unit_id": obs.get("evidence_unit_id"),
            "semantic_observation_id": obs.get("id"),
            "occurrence_phase": obs.get("occurrence_phase") or "reference",
            "occurrence_role": occurrence_role,
            "observed_text": str((attrs or {}).get("evidence_text") or obs.get("observed_name") or "")[:2000],
            "observed_type": obs.get("observed_type"),
            "scope_json": {},
            "attributes": {"normalized_by": C0_VERSION, "semantic_role": semantic_role},
            "confidence": obs.get("model_confidence"),
            "occurrence_hash": occurrence_hash,
        })
        link_context = {
            "requirement_occurrence_id": occurrence_id,
            "semantic_role": "requirement" if occurrence_role == "requirement" else occurrence_role,
            "normalized_by": C0_VERSION,
        }
        evidence_links.append({
            "project_id": project_id,
            "object_entity_id": target.get("entity_id"),
            "domain_table": "project_requirements",
            "domain_id": target.get("id"),
            "evidence_unit_id": obs.get("evidence_unit_id"),
            "link_role": "occurrence",
            "context": link_context,
            "context_sha256": _sha(link_context),
            "binding_confidence": obs.get("model_confidence"),
        })
        resolutions.append({
            "id": obs["id"], "status": "reconciled", "resolution_action": resolution_action,
            "resolved_entity_id": target.get("entity_id"), "resolved_domain_table": "project_requirements", "resolved_domain_id": target.get("id"),
            "resolution_detail": {"reason": resolution.get("reason"), "score": resolution.get("score"), "semantic_role": semantic_role},
        })

    return {
        "requirements": list({row["id"]: row for row in new_requirements}.values()),
        "occurrences": list({row["id"]: row for row in occurrences}.values()),
        "observation_resolutions": resolutions,
        "evidence_links": list({(row["object_entity_id"], row["evidence_unit_id"], row["context_sha256"]): row for row in evidence_links}.values()),
        "blocked_existing_ids": sorted(blocked_existing_ids),
    }


def _start_run(client: Any, project_id: str, project_entity_id: str, signature: Any) -> str:
    run_id = str(uuid4())
    payload = {
        "id": run_id,
        "analyzer_type": "project_requirement_reconciliation",
        "scope_kind": "project",
        "scope_entity_id": project_entity_id,
        "pipeline_version": C0_VERSION,
        "code_version": C0_VERSION,
        "schema_version": C0_SCHEMA_VERSION,
        "input_signature": _sha(signature),
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {"project_id": project_id, "legacy_shadow": True, "auto_merge_existing_requirements": False},
    }
    rows = _rows(client.table("intelligence_runs").insert(payload).execute())
    if not rows:
        raise RuntimeError("Supabase não confirmou intelligence_run de Requirement Reconciliation")
    return str(rows[0].get("id") or run_id)


def _mark_run_error(client: Any, run_id: str, exc: Exception) -> None:
    try:
        client.table("intelligence_runs").update({
            "status": "error", "completed_at": datetime.now(timezone.utc).isoformat(),
            "error_code": "requirement_reconciliation_error", "error_detail": str(exc)[:4000],
        }).eq("id", run_id).execute()
    except Exception:
        pass


def fetch_project_requirement_reconciliation_status(client: Any, project_id: str) -> dict[str, Any]:
    rows = _rows(client.table("project_requirement_reconciliation_status").select("*").eq("project_id", project_id).limit(1).execute())
    return rows[0] if rows else {"project_id": project_id}


def reconcile_project_requirements(client: Any, project_id: str) -> dict[str, Any]:
    probe = probe_requirement_reconciliation_schema(client)
    if not probe.get("available"):
        return {"project_id": project_id, "status": probe.get("status"), "warnings": [probe.get("error")]}
    project_entity = _project_entity(client, project_id)
    if not project_entity:
        return {"project_id": project_id, "status": "blocked", "warnings": ["Project knowledge_entity mirror ausente."]}

    extraction = collect_project_requirement_observations(client, project_id)
    observations = extraction.get("observations") or []
    existing = _read_rows(client, "project_requirements", equals={"project_id": project_id})
    # Fail closed: a project that already carries legacy Requirements may never be
    # "reconciled" by an empty observation bundle caused by a missing briefing/source.
    if existing and not observations:
        return {
            "project_id": project_id,
            "status": "blocked_empty_requirement_observation_bundle",
            "warnings": ["C0.2.4 não encontrou Evidence-backed Requirement observations; estado anterior preservado."],
            "diagnostics": extraction.get("diagnostics") or [],
        }
    plan = build_requirement_reconciliation_plan(project_id, observations, existing)
    bundle = {
        "version": C0_VERSION,
        "project_entity_id": str(project_entity.get("id")),
        "observations": observations,
        **plan,
    }
    run_id = _start_run(client, project_id, str(project_entity.get("id")), {
        "observations": [(row.get("observation_hash"), row.get("semantic_role")) for row in observations],
        "existing_requirements": [(row.get("id"), row.get("title"), row.get("legacy_source_id")) for row in existing],
    })
    try:
        response = client.rpc(C0_RPC, {"p_project_id": project_id, "p_run_id": run_id, "p_bundle": bundle}).execute()
        rpc_rows = _rows(response)
        status = fetch_project_requirement_reconciliation_status(client, project_id)
        classified = {
            "scopes": [str(row.get("observed_name")) for row in observations if str(row.get("semantic_role")) in SCOPE_ROLES],
            "attributes": [str(row.get("observed_name")) for row in observations if str(row.get("semantic_role")) in ATTRIBUTE_ROLES],
            "contexts": [str(row.get("observed_name")) for row in observations if str(row.get("semantic_role")) in CONTEXT_ROLES],
            "references": [str(row.get("observed_name")) for row in observations if str(row.get("semantic_role")) in REFERENCE_ROLES],
            "suggestions": [str(row.get("observed_name")) for row in observations if str(row.get("semantic_role")) == "suggestion_signal"],
            "examples": [str(row.get("observed_name")) for row in observations if str(row.get("semantic_role")) == "example_signal"],
            "parameters": [str(row.get("observed_name")) for row in observations if str(row.get("semantic_role")) == "parameter_signal"],
            "constraint_qualifiers": [str(row.get("observed_name")) for row in observations if str(row.get("semantic_role")) == "constraint_qualifier"],
            "evidence_first": [str(row.get("observed_name")) for row in observations if str((row.get("attributes") or {}).get("origin_route")) == "evidence_first"],
            "blocked_legacy_identity_ids": list(plan.get("blocked_existing_ids") or []),
        }
        gate = _semantic_gate(status)
        return {
            "project_id": project_id,
            "status": "completed" if gate["pass"] else "semantic_gate_blocked",
            "run_id": run_id,
            "rpc": rpc_rows[0] if rpc_rows else {},
            "requirement_reconciliation": status,
            "semantic_gate": gate,
            "actions": {
                "observations": len(observations),
                "new_requirements": len(plan.get("requirements") or []),
                "occurrences": len(plan.get("occurrences") or []),
                "review_required": sum(1 for row in plan.get("observation_resolutions") or [] if row.get("status") == "review_required"),
                "no_domain_object": sum(1 for row in plan.get("observation_resolutions") or [] if row.get("status") == "no_domain_object"),
                "semantic_gate_blockers": gate["blockers"],
                "new_requirement_titles": [str(row.get("title")) for row in plan.get("requirements") or []],
                **classified,
            },
            "diagnostics": extraction.get("diagnostics") or [],
            "extraction_summary": extraction.get("summary") or {},
            "warnings": [] if gate["pass"] else [
                "Requirement Semantic Gate bloqueou V28.7.2B: " + json.dumps(gate["components"], ensure_ascii=False, sort_keys=True)
            ],
        }
    except Exception as exc:
        _mark_run_error(client, run_id, exc)
        return {"project_id": project_id, "status": "transaction_error", "run_id": run_id, "warnings": [str(exc)]}
