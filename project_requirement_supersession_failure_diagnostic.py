from __future__ import annotations

"""NAVE V28.7.3B2.12.5.2 — Failed Supersession State Diagnostic.

READ ONLY. Designed specifically for the state immediately after a B2.12.5.x RPC error.
It never calls the writer and never mutates Requirement/Response Truth.

The diagnostic consumes the exact preflight JSON that the user reviewed, so it can
compare persisted state against BOTH the expected pre-write state and expected
post-transaction state without hardcoding Golden project IDs.
"""

from typing import Any, Mapping, Sequence

from project_domain_reader import get_cutover_state
from project_requirement_identity_collision_shadow import run_identity_collision_shadow
from project_requirement_compatibility import load_requirement_compatibility, compatibility_alias_maps

VERSION = "V28.7.3B2.12.5.2"
WRITER_VERSIONS = {"V28.7.3B2.12.5", "V28.7.3B2.12.5.1"}
CURRENT_TRUTH = {"verified", "human_confirmed"}


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, Mapping):
        return [dict(data)]
    return [dict(row) for row in (data or []) if isinstance(row, Mapping)]


def _truth(row: Mapping[str, Any] | None) -> str:
    row = row or {}
    return str(row.get("truth_state") or row.get("verification_state") or "").casefold()


def _eq(value: Any, expected: Any) -> bool:
    return str(value or "") == str(expected or "")


def _active_occurrence(row: Mapping[str, Any] | None) -> bool:
    row = row or {}
    return str(row.get("lifecycle_status") or "active").casefold() == "active"


def _one(rows: Sequence[Mapping[str, Any]], key: str, value: str) -> dict[str, Any] | None:
    matches = [dict(row) for row in rows if str(row.get(key) or "") == str(value)]
    return matches[0] if len(matches) == 1 else None


def diagnose_failed_supersession(
    client: Any,
    *,
    preflight: Mapping[str, Any],
) -> dict[str, Any]:
    project_id = str(preflight.get("project_id") or "")
    plan = dict(preflight.get("execution_plan") or {})
    dry = dict(preflight.get("dry_run_report") or {})

    if not project_id or not plan:
        raise ValueError("B2.12.5.2 requires a READY preflight JSON with execution_plan")

    survivor_id = str(plan.get("survivor_requirement_id") or "")
    survivor_entity_id = str(plan.get("survivor_entity_id") or "")
    old_ids = [str(v) for v in (plan.get("superseded_requirement_ids") or []) if v]
    old_entity_ids = [str(v) for v in (plan.get("superseded_entity_ids") or []) if v]
    aliases = [
        str(row.get("alias") or "")
        for row in (plan.get("alias_actions") or [])
        if row.get("alias")
    ]
    occurrence_plan = [dict(row) for row in (plan.get("occurrence_actions") or [])]
    semantic_plan = [dict(row) for row in (plan.get("semantic_observation_actions") or [])]

    if len(old_ids) != 1 or len(old_entity_ids) != 1:
        raise ValueError("B2.12.5.2 incident diagnostic currently requires exactly one superseded identity")

    old_id = old_ids[0]
    old_entity_id = old_entity_ids[0]

    truth_rows = _rows(
        client.table("project_requirement_truth_status")
        .select("*").eq("project_id", project_id).execute()
    )
    requirement_rows = _rows(
        client.table("project_requirements")
        .select("*").eq("project_id", project_id).execute()
    )
    occurrence_rows = _rows(
        client.table("project_requirement_occurrences")
        .select("*").eq("project_id", project_id).execute()
    )
    evidence_rows = _rows(
        client.table("domain_object_evidence")
        .select("*").eq("project_id", project_id)
        .eq("domain_table", "project_requirements").execute()
    )
    semantic_rows = _rows(
        client.table("semantic_observations")
        .select("*").eq("project_id", project_id)
        .eq("domain_hint", "requirement").execute()
    )

    entity_ids = [survivor_entity_id, old_entity_id]
    governance_rows = _rows(
        client.table("domain_object_governance")
        .select("*").in_("entity_id", entity_ids).execute()
    )
    knowledge_rows = _rows(
        client.table("knowledge_entities")
        .select("*").in_("id", entity_ids).execute()
    )

    # Writer audit rows. A DB exception inside the transactional RPC should roll
    # this row back too; if a completed row exists, the HTTP error may have occurred
    # after the DB transaction completed and persisted.
    run_rows = _rows(
        client.table("intelligence_runs")
        .select("*")
        .eq("analyzer_type", "project_requirement_identity_supersession")
        .order("started_at", desc=True)
        .limit(100)
        .execute()
    )
    project_runs = [
        row for row in run_rows
        if str((row.get("metadata") or {}).get("project_id") or "") == project_id
    ]
    fingerprint = str(preflight.get("review_fingerprint") or "")
    matching_runs = [
        row for row in project_runs
        if not fingerprint
        or str((row.get("metadata") or {}).get("review_fingerprint") or "") == fingerprint
    ]
    latest_matching_run = matching_runs[0] if matching_runs else None

    truth_by_id = {str(row.get("id") or ""): row for row in truth_rows if row.get("id")}
    req_by_id = {str(row.get("id") or ""): row for row in requirement_rows if row.get("id")}
    gov_by_entity = {str(row.get("entity_id") or ""): row for row in governance_rows if row.get("entity_id")}
    ke_by_id = {str(row.get("id") or ""): row for row in knowledge_rows if row.get("id")}

    survivor_truth = truth_by_id.get(survivor_id)
    old_truth = truth_by_id.get(old_id)
    survivor_req = req_by_id.get(survivor_id)
    old_req = req_by_id.get(old_id)
    survivor_gov = gov_by_entity.get(survivor_entity_id)
    old_gov = gov_by_entity.get(old_entity_id)
    survivor_ke = ke_by_id.get(survivor_entity_id)
    old_ke = ke_by_id.get(old_entity_id)

    current_count = sum(1 for row in truth_rows if _truth(row) in CURRENT_TRUTH)
    expected_before = int(dry.get("current_requirement_count_before") or plan.get("current_before") or 0)
    expected_after = int(dry.get("projected_current_requirement_count_after") or plan.get("projected_current_after") or 0)
    expected_collision_before = int(dry.get("collision_count_before") or 0)
    expected_collision_after = int(dry.get("projected_collision_count_after") or 0)

    collision = run_identity_collision_shadow(client, project_id=project_id)
    collision_count = int(collision.collision_count)

    planned_old_occurrence_ids = {
        str(row.get("occurrence_id") or "") for row in occurrence_plan if row.get("occurrence_id")
    }
    old_occurrences = [
        row for row in occurrence_rows
        if str(row.get("id") or "") in planned_old_occurrence_ids
    ]
    old_occurrence_active = bool(old_occurrences) and all(_active_occurrence(row) for row in old_occurrences)
    old_occurrence_superseded = bool(old_occurrences) and all(
        str(row.get("lifecycle_status") or "").casefold() == "superseded"
        for row in old_occurrences
    )

    old_evidence_count = sum(
        1 for row in evidence_rows
        if str(row.get("object_entity_id") or "") == old_entity_id
    )
    expected_old_evidence_count = int(plan.get("raw_historical_evidence_link_count") or 0)

    planned_semantic_ids = {
        str(row.get("semantic_observation_id") or "")
        for row in semantic_plan if row.get("semantic_observation_id")
    }
    semantic_matches = [
        row for row in semantic_rows
        if str(row.get("id") or "") in planned_semantic_ids
    ]
    semantic_count = len(semantic_matches)

    writer_source_links = []
    writer_occurrence_links = []
    for row in evidence_rows:
        context = row.get("context") if isinstance(row.get("context"), Mapping) else {}
        identity_resolution = context.get("identity_resolution") if isinstance(context.get("identity_resolution"), Mapping) else {}
        if str(identity_resolution.get("canonical_requirement_id") or "") != survivor_id:
            continue
        if str(identity_resolution.get("version") or "") not in WRITER_VERSIONS:
            continue
        if str(row.get("link_role") or "") == "source":
            writer_source_links.append(row)
        if str(row.get("link_role") or "") == "occurrence":
            writer_occurrence_links.append(row)

    # Structural alias resolution via B2.1. Any error is diagnostic data, never a write.
    alias_map_error = None
    legacy_to_domain: dict[str, str] = {}
    try:
        compat = load_requirement_compatibility(client, project_id=project_id)
        legacy_to_domain, _ = compatibility_alias_maps(compat)
        compat_summary = {
            "status": "PASS_DATA_BRIDGE" if compat.pass_data_bridge else "BLOCKED",
            "active_links": compat.active_link_count,
            "resolved_active_links": compat.resolved_active_link_count,
            "unmapped": compat.active_links_unmapped,
            "ambiguous": compat.active_links_ambiguous,
        }
    except Exception as exc:
        alias_map_error = str(exc)
        compat_summary = {"status": "ERROR", "error": alias_map_error}

    alias_targets = {alias: legacy_to_domain.get(alias) for alias in aliases}
    aliases_to_survivor = all(alias_targets.get(alias) == survivor_id for alias in aliases) if aliases else True
    aliases_to_old = all(alias_targets.get(alias) == old_id for alias in aliases) if aliases else True

    state = get_cutover_state(client, project_id, "requirements")
    read_mode = str(state.get("read_mode") or "")

    prewrite_checks = {
        "current_count_is_prewrite": current_count == expected_before,
        "collision_count_is_prewrite": collision_count == expected_collision_before,
        "survivor_is_current": _truth(survivor_truth) in CURRENT_TRUTH,
        "survivor_requirement_active": str((survivor_req or {}).get("status") or "active") == "active",
        "old_identity_is_still_current": _truth(old_truth) in CURRENT_TRUTH,
        "old_requirement_is_active": str((old_req or {}).get("status") or "active") == "active",
        "old_governance_is_active": str((old_gov or {}).get("lifecycle_status") or "active") == "active",
        "old_governance_not_superseded": not bool((old_gov or {}).get("superseded_by_entity_id")),
        "old_knowledge_entity_not_merged": str((old_ke or {}).get("status") or "active") != "merged",
        "old_occurrence_is_active": old_occurrence_active,
        "historical_old_evidence_count_unchanged": old_evidence_count == expected_old_evidence_count,
        "semantic_observations_still_present": semantic_count == len(planned_semantic_ids),
        "no_writer_source_evidence_present": len(writer_source_links) == 0,
        "no_completed_matching_writer_run": not (
            latest_matching_run and str(latest_matching_run.get("status") or "") == "completed"
        ),
        "read_mode_still_shadow_compare": read_mode == "shadow_compare",
    }

    postwrite_checks = {
        "current_count_is_postwrite": current_count == expected_after,
        "collision_count_is_postwrite": collision_count == expected_collision_after,
        "survivor_is_current": _truth(survivor_truth) in CURRENT_TRUTH,
        "survivor_requirement_active": str((survivor_req or {}).get("status") or "active") == "active",
        "old_identity_is_historical": _truth(old_truth) == "historical",
        "old_requirement_superseded": str((old_req or {}).get("status") or "") == "superseded",
        "old_governance_superseded_to_survivor": (
            str((old_gov or {}).get("lifecycle_status") or "") == "superseded"
            and _eq((old_gov or {}).get("superseded_by_entity_id"), survivor_entity_id)
        ),
        "old_knowledge_entity_merged_to_survivor": (
            str((old_ke or {}).get("status") or "") == "merged"
            and _eq((old_ke or {}).get("canonical_entity_id"), survivor_entity_id)
        ),
        "old_occurrence_superseded": old_occurrence_superseded,
        "aliases_resolve_to_survivor": aliases_to_survivor,
        "historical_old_evidence_count_unchanged": old_evidence_count == expected_old_evidence_count,
        "semantic_observations_still_present": semantic_count == len(planned_semantic_ids),
        "writer_created_no_occurrence_evidence": len(writer_occurrence_links) == 0,
        "completed_matching_writer_run_exists": bool(
            latest_matching_run and str(latest_matching_run.get("status") or "") == "completed"
        ),
        "read_mode_still_shadow_compare": read_mode == "shadow_compare",
    }

    prewrite_pass = all(prewrite_checks.values())
    postwrite_pass = all(postwrite_checks.values())

    if prewrite_pass and not postwrite_pass:
        classification = "CONFIRMED_PREWRITE_STATE_INTACT"
    elif postwrite_pass and not prewrite_pass:
        classification = "CONFIRMED_TRANSACTION_COMPLETED_STATE"
    elif prewrite_pass and postwrite_pass:
        classification = "AMBIGUOUS_BOTH_STATE_MODELS_PASS"
    else:
        classification = "PARTIAL_OR_UNEXPECTED_STATE"

    return {
        "version": VERSION,
        "project_id": project_id,
        "classification": classification,
        "safe_to_retry_writer": False,
        "retry_policy": "NEVER_RETRY_FROM_THIS_DIAGNOSTIC; investigate root cause first",
        "review_fingerprint": fingerprint or None,
        "current_requirement_count": current_count,
        "expected_current_before": expected_before,
        "expected_current_after": expected_after,
        "canonical_collision_count": collision_count,
        "expected_collision_before": expected_collision_before,
        "expected_collision_after": expected_collision_after,
        "survivor": {
            "requirement_id": survivor_id,
            "entity_id": survivor_entity_id,
            "truth_state": _truth(survivor_truth),
            "requirement_status": (survivor_req or {}).get("status"),
            "legacy_source_id": (survivor_req or {}).get("legacy_source_id"),
            "governance_lifecycle": (survivor_gov or {}).get("lifecycle_status"),
            "knowledge_entity_status": (survivor_ke or {}).get("status"),
            "canonical_entity_id": (survivor_ke or {}).get("canonical_entity_id"),
        },
        "superseded_candidate": {
            "requirement_id": old_id,
            "entity_id": old_entity_id,
            "truth_state": _truth(old_truth),
            "requirement_status": (old_req or {}).get("status"),
            "legacy_source_id": (old_req or {}).get("legacy_source_id"),
            "governance_lifecycle": (old_gov or {}).get("lifecycle_status"),
            "superseded_by_entity_id": (old_gov or {}).get("superseded_by_entity_id"),
            "knowledge_entity_status": (old_ke or {}).get("status"),
            "canonical_entity_id": (old_ke or {}).get("canonical_entity_id"),
            "planned_occurrences": [
                {
                    "id": row.get("id"),
                    "requirement_id": row.get("requirement_id"),
                    "lifecycle_status": row.get("lifecycle_status"),
                    "occurrence_hash": row.get("occurrence_hash"),
                }
                for row in old_occurrences
            ],
        },
        "legacy_aliases": aliases,
        "alias_targets": alias_targets,
        "alias_map_error": alias_map_error,
        "compatibility": compat_summary,
        "historical_old_evidence_count": old_evidence_count,
        "expected_historical_old_evidence_count": expected_old_evidence_count,
        "planned_semantic_observation_count": len(planned_semantic_ids),
        "semantic_observations_found": semantic_count,
        "writer_source_evidence_links_found": len(writer_source_links),
        "writer_occurrence_evidence_links_found": len(writer_occurrence_links),
        "latest_matching_writer_run": (
            {
                "id": latest_matching_run.get("id"),
                "status": latest_matching_run.get("status"),
                "pipeline_version": latest_matching_run.get("pipeline_version"),
                "started_at": latest_matching_run.get("started_at"),
                "completed_at": latest_matching_run.get("completed_at"),
                "error_code": latest_matching_run.get("error_code"),
                "error_detail": latest_matching_run.get("error_detail"),
            }
            if latest_matching_run else None
        ),
        "requirements_read_mode": read_mode,
        "prewrite_model": {
            "all_checks_pass": prewrite_pass,
            "checks": prewrite_checks,
            "aliases_currently_resolve_to_old": aliases_to_old,
        },
        "postwrite_model": {
            "all_checks_pass": postwrite_pass,
            "checks": postwrite_checks,
        },
        "writes_performed_by_diagnostic": False,
        "writer_called_by_diagnostic": False,
        "truth_changed_by_diagnostic": False,
        "cutover_changed_by_diagnostic": False,
    }
