from __future__ import annotations

"""Independent read-only post-transaction verifier for B2.12.5."""

from typing import Any, Mapping

from project_domain_reader import get_cutover_state
from project_intelligence_pipeline import requirement_reconciliation_contract
from project_requirement_compatibility import (
    compatibility_alias_maps,
    load_requirement_compatibility,
)
from project_requirement_identity_collision_shadow import run_identity_collision_shadow

VERSION = "V28.7.3B2.12.5V1"
WRITER_VERSION = "V28.7.3B2.12.5.1"
PROMOTION_VERSION = "V28.7.2C0.2.4H3.1.3P1"


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, Mapping):
        return [dict(data)]
    return [
        dict(row)
        for row in (data or [])
        if isinstance(row, Mapping)
    ]


def verify_supersession(
    client: Any,
    *,
    project_id: str,
) -> dict[str, Any]:
    runs = _rows(
        client.table("intelligence_runs")
        .select("*")
        .eq("analyzer_type", "project_requirement_identity_supersession")
        .order("started_at", desc=True)
        .limit(100)
        .execute()
    )
    project_runs = [
        row
        for row in runs
        if str((row.get("metadata") or {}).get("project_id") or "") == str(project_id)
    ]
    if not project_runs:
        return {
            "version": VERSION,
            "project_id": project_id,
            "status": "NO_SUPERSESSION_RUN",
            "all_checks_pass": False,
            "failed_checks": ["no_completed_supersession_run"],
            "writes_performed_by_verifier": False,
        }

    run = project_runs[0]
    metadata = dict(run.get("metadata") or {})
    survivor_id = str(metadata.get("survivor_requirement_id") or "")
    survivor_entity_id = str(metadata.get("survivor_entity_id") or "")
    old_ids = [
        str(value)
        for value in (metadata.get("superseded_requirement_ids") or [])
        if value
    ]
    old_entity_ids = [
        str(value)
        for value in (metadata.get("superseded_entity_ids") or [])
        if value
    ]
    aliases = [
        str(value)
        for value in (metadata.get("legacy_aliases") or [])
        if value
    ]
    expected_current = int(metadata.get("expected_current_after") or 0)

    truth = _rows(
        client.table("project_requirement_truth_status")
        .select("*")
        .eq("project_id", project_id)
        .execute()
    )
    requirements = _rows(
        client.table("project_requirements")
        .select("*")
        .eq("project_id", project_id)
        .execute()
    )
    occurrences = _rows(
        client.table("project_requirement_occurrences")
        .select("*")
        .eq("project_id", project_id)
        .execute()
    )
    evidence = _rows(
        client.table("domain_object_evidence")
        .select("*")
        .eq("project_id", project_id)
        .eq("domain_table", "project_requirements")
        .execute()
    )
    semantics = _rows(
        client.table("semantic_observations")
        .select("*")
        .eq("project_id", project_id)
        .eq("domain_hint", "requirement")
        .execute()
    )

    entity_ids = [survivor_entity_id, *old_entity_ids]
    governance: list[dict[str, Any]] = []
    knowledge: list[dict[str, Any]] = []
    if entity_ids:
        governance = _rows(
            client.table("domain_object_governance")
            .select("*")
            .in_("entity_id", entity_ids)
            .execute()
        )
        knowledge = _rows(
            client.table("knowledge_entities")
            .select("*")
            .in_("id", entity_ids)
            .execute()
        )

    state = get_cutover_state(client, project_id, "requirements")
    pipeline_contract = requirement_reconciliation_contract()
    collision = run_identity_collision_shadow(
        client,
        project_id=project_id,
    )
    compat = load_requirement_compatibility(
        client,
        project_id=project_id,
    )
    alias_map_error = None
    try:
        legacy_to_domain, _ = compatibility_alias_maps(compat)
    except Exception as exc:
        legacy_to_domain = {}
        alias_map_error = str(exc)

    current_rows = [
        row
        for row in truth
        if str(row.get("truth_state") or "") in {"verified", "human_confirmed"}
    ]
    truth_by_id = {
        str(row.get("id") or ""): row
        for row in truth
        if row.get("id")
    }
    req_by_id = {
        str(row.get("id") or ""): row
        for row in requirements
        if row.get("id")
    }
    gov_by_entity = {
        str(row.get("entity_id") or ""): row
        for row in governance
        if row.get("entity_id")
    }
    ke_by_id = {
        str(row.get("id") or ""): row
        for row in knowledge
        if row.get("id")
    }

    old_evidence_count = sum(
        1
        for row in evidence
        if str(row.get("object_entity_id") or "") in set(old_entity_ids)
    )
    old_semantic_count = sum(
        1
        for row in semantics
        if str(row.get("resolved_domain_id") or "") in set(old_ids)
    )
    run_source_links = [
        row
        for row in evidence
        if str(row.get("normalization_run_id") or "") == str(run.get("id") or "")
        and str(row.get("link_role") or "") == "source"
    ]
    run_occurrence_links = [
        row
        for row in evidence
        if str(row.get("normalization_run_id") or "") == str(run.get("id") or "")
        and str(row.get("link_role") or "") == "occurrence"
    ]

    checks: dict[str, bool] = {
        "writer_run_completed": (
            str(run.get("status") or "") == "completed"
            and str(run.get("pipeline_version") or "") == WRITER_VERSION
        ),
        "current_count_matches_postcondition": len(current_rows) == expected_current,
        "survivor_is_current": str(
            truth_by_id.get(survivor_id, {}).get("truth_state") or ""
        ) in {"verified", "human_confirmed"},
        "all_superseded_are_historical": all(
            str(truth_by_id.get(rid, {}).get("truth_state") or "") == "historical"
            for rid in old_ids
        ),
        "all_old_requirement_status_superseded": all(
            str(req_by_id.get(rid, {}).get("status") or "") == "superseded"
            for rid in old_ids
        ),
        "governance_lineage_complete": all(
            str(gov_by_entity.get(eid, {}).get("lifecycle_status") or "") == "superseded"
            and str(gov_by_entity.get(eid, {}).get("superseded_by_entity_id") or "")
                == survivor_entity_id
            for eid in old_entity_ids
        ),
        "knowledge_entity_lineage_complete": all(
            str(ke_by_id.get(eid, {}).get("status") or "") == "merged"
            and str(ke_by_id.get(eid, {}).get("canonical_entity_id") or "")
                == survivor_entity_id
            for eid in old_entity_ids
        ),
        "no_active_occurrence_on_old_identity": not any(
            str(row.get("requirement_id") or "") in set(old_ids)
            and str(row.get("lifecycle_status") or "active") == "active"
            for row in occurrences
        ),
        "canonical_collision_count_zero": collision.collision_count == 0,
        "b2_1_compatibility_pass": compat.pass_data_bridge,
        "all_legacy_aliases_uniquely_resolve_to_survivor": (
            alias_map_error is None
            and all(
                legacy_to_domain.get(alias) == survivor_id
                for alias in aliases
            )
        ),
        "historical_evidence_count_preserved": (
            old_evidence_count == int(metadata.get("old_evidence_count_before") or 0)
        ),
        "historical_semantic_observation_count_preserved": (
            old_semantic_count
            == int(metadata.get("semantic_observation_count_before") or 0)
        ),
        "writer_created_no_occurrence_evidence_links": len(run_occurrence_links) == 0,
        "writer_source_link_count_matches_audit": (
            len(run_source_links)
            == int(metadata.get("source_evidence_links_inserted") or 0)
        ),
        "survivor_business_metadata_preserved": bool(
            metadata.get("survivor_business_metadata_preserved")
        ),
        "response_truth_not_changed_by_contract": metadata.get("response_truth_changed") is False,
        "human_review_not_created": metadata.get("human_review_created") is False,
        "requirements_still_shadow_compare": str(state.get("read_mode") or "") == "shadow_compare",
        "normal_pipeline_still_h31": (
            pipeline_contract.get("normal_pipeline_uses_h31") is True
            and str(pipeline_contract.get("promotion_version") or "") == PROMOTION_VERSION
        ),
    }

    failed = [key for key, value in checks.items() if not value]

    return {
        "version": VERSION,
        "writer_version": WRITER_VERSION,
        "project_id": project_id,
        "run_id": run.get("id"),
        "status": "PASS_POST_TRANSACTION_VERIFICATION" if not failed else "BLOCKED_POST_TRANSACTION_VERIFICATION",
        "all_checks_pass": not failed,
        "failed_checks": failed,
        "checks": checks,
        "current_requirement_count": len(current_rows),
        "canonical_collision_count": collision.collision_count,
        "compatibility": {
            "status": "PASS_DATA_BRIDGE" if compat.pass_data_bridge else "BLOCKED",
            "active_links": compat.active_link_count,
            "resolved_active_links": compat.resolved_active_link_count,
            "unmapped": compat.active_links_unmapped,
            "ambiguous": compat.active_links_ambiguous,
        },
        "survivor_requirement_id": survivor_id,
        "superseded_requirement_ids": old_ids,
        "legacy_aliases": aliases,
        "alias_map_error": alias_map_error,
        "historical_evidence_count": old_evidence_count,
        "historical_semantic_observation_count": old_semantic_count,
        "writer_source_links": len(run_source_links),
        "writer_occurrence_links": len(run_occurrence_links),
        "requirements_read_mode": state.get("read_mode"),
        "requirement_truth_changed": True,
        "response_truth_changed": False,
        "writes_performed_by_verifier": False,
        "cutover_changed_by_verifier": False,
    }
