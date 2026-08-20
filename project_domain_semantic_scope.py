from __future__ import annotations

"""NAVE V28.7.3A3.1 — semantic subject / lifecycle binding for A3.

This module is comparator-only infrastructure. It reads Domain identity/occurrence
rows needed to determine *what subject* an outcome belongs to before the
Semantic Shadow Comparator compares categorical values.

It never mutates Truth, readiness, read_mode, Graph or legacy data.
"""

from collections.abc import Mapping, Sequence
from typing import Any

SCOPE_BINDING_VERSION = "V28.7.3A3.1"


class SemanticScopeError(RuntimeError):
    """Fail-closed subject-binding read failure."""


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, Mapping):
        return [dict(data)]
    return [dict(row) for row in (data or []) if isinstance(row, Mapping)]


def _read_project_rows(client: Any, table_name: str, project_id: str) -> list[dict[str, Any]]:
    try:
        return _rows(
            client.table(table_name)
            .select("*")
            .eq("project_id", project_id)
            .execute()
        )
    except Exception as exc:  # runtime integration path
        raise SemanticScopeError(
            f"Semantic scope binding failed reading {table_name!r} for project {project_id}: {exc}"
        ) from exc


def build_semantic_scope_snapshot(client: Any, project_id: str) -> dict[str, Any]:
    """Read only the Domain rows required to bind outcome subjects/lifecycle."""
    return {
        "project_id": project_id,
        "solution_instances": _read_project_rows(client, "project_solution_instances", project_id),
        "solution_occurrences": _read_project_rows(client, "project_solution_occurrences", project_id),
        "binding_version": SCOPE_BINDING_VERSION,
    }


def _as_ids(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return {value} if value.strip() else set()
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return {str(item) for item in value if item}
    return set()


def _outcome_dimension(row: Mapping[str, Any]) -> str:
    return str(
        row.get("outcome_type")
        or row.get("outcome_key")
        or row.get("outcome_name")
        or row.get("_legacy_outcome_dimension")
        or ""
    ).strip().casefold()


def _material_feedback(row: Mapping[str, Any]) -> bool:
    source = str(row.get("information_source") or "").strip().casefold()
    if source != "client_feedback":
        return False
    return any(
        str(row.get(key) or "").strip()
        for key in (
            "decision_reason",
            "feedback_summary",
            "result_context",
            "execution_notes",
            "reason",
            "notes",
        )
    )


def bind_semantic_subjects(
    domain_key: str,
    domain_rows: Sequence[Mapping[str, Any]],
    legacy_rows: Sequence[Mapping[str, Any]],
    *,
    project_id: str,
    scope_snapshot: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Decorate rows with comparator-only subject/lifecycle metadata.

    A3.1 uses this metadata only for semantic comparison. No persisted Domain or
    Legacy row is modified.
    """
    domain = [dict(row) for row in domain_rows if isinstance(row, Mapping)]
    legacy = [dict(row) for row in legacy_rows if isinstance(row, Mapping)]

    if domain_key != "outcomes":
        return domain, legacy

    solution_instances = [
        dict(row)
        for row in (scope_snapshot.get("solution_instances") or [])
        if isinstance(row, Mapping)
    ]
    occurrences = [
        dict(row)
        for row in (scope_snapshot.get("solution_occurrences") or [])
        if isinstance(row, Mapping)
    ]

    entity_to_solution: dict[str, dict[str, Any]] = {}
    legacy_item_to_entities: dict[str, set[str]] = {}
    solution_id_to_entity: dict[str, str] = {}

    for solution in solution_instances:
        entity_id = str(solution.get("entity_id") or "").strip()
        solution_id = str(solution.get("id") or "").strip()
        if entity_id:
            entity_to_solution[entity_id] = solution
        if solution_id and entity_id:
            solution_id_to_entity[solution_id] = entity_id

        legacy_ids = set()
        legacy_ids.update(_as_ids(solution.get("legacy_source_ids")))
        attributes = solution.get("attributes") or {}
        if isinstance(attributes, Mapping):
            legacy_ids.update(_as_ids(attributes.get("legacy_memory_item_ids")))
        for legacy_id in legacy_ids:
            if entity_id:
                legacy_item_to_entities.setdefault(legacy_id, set()).add(entity_id)

    evidence_to_occurrences: dict[str, list[dict[str, Any]]] = {}
    for occurrence in occurrences:
        if str(occurrence.get("lifecycle_status") or "active").casefold() == "invalidated":
            continue
        evidence_id = str(occurrence.get("evidence_unit_id") or "").strip()
        if evidence_id:
            evidence_to_occurrences.setdefault(evidence_id, []).append(occurrence)

    # Infer the project-level semantic entity from dimensions that are inherently
    # project-scoped. This avoids assuming project_id == entity_id.
    project_entity_ids = {
        str(row.get("entity_id") or "").strip()
        for row in domain
        if _outcome_dimension(row) in {"process_type", "commercial_result"}
        and str(row.get("entity_id") or "").strip()
    }

    for row in domain:
        entity_id = str(row.get("entity_id") or "").strip()
        dimension = _outcome_dimension(row)
        solution = entity_to_solution.get(entity_id)

        if solution is not None:
            row["_semantic_subject_kind"] = "solution"
            row["_semantic_subject_key"] = f"solution:{entity_id}"
            row["_semantic_subject_name"] = str(solution.get("name") or "").strip() or None
            row["_semantic_solution_instance_id"] = str(solution.get("id") or "").strip() or None
            row["_semantic_subject_binding"] = "domain_entity_id_to_solution_entity_id"
        elif dimension in {"process_type", "commercial_result"} or entity_id in project_entity_ids:
            row["_semantic_subject_kind"] = "project"
            row["_semantic_subject_key"] = f"project:{project_id}"
            row["_semantic_subject_name"] = None
            row["_semantic_subject_binding"] = "project_scoped_outcome_dimension"
        elif entity_id:
            row["_semantic_subject_kind"] = "entity"
            row["_semantic_subject_key"] = f"entity:{entity_id}"
            row["_semantic_subject_name"] = None
            row["_semantic_subject_binding"] = "unresolved_domain_entity"
        else:
            row["_semantic_subject_kind"] = "unknown"
            row["_semantic_subject_key"] = None
            row["_semantic_subject_name"] = None
            row["_semantic_subject_binding"] = "missing_domain_entity_id"

        evidence_id = str(row.get("source_evidence_id") or "").strip()
        matching_occurrences = evidence_to_occurrences.get(evidence_id, []) if evidence_id else []
        selected_occurrence = None
        if matching_occurrences:
            solution_instance_id = str(row.get("_semantic_solution_instance_id") or "")
            for occurrence in matching_occurrences:
                if str(occurrence.get("solution_instance_id") or "") == solution_instance_id:
                    selected_occurrence = occurrence
                    break
            if selected_occurrence is None and len(matching_occurrences) == 1:
                selected_occurrence = matching_occurrences[0]

        if selected_occurrence:
            row["_semantic_lifecycle_phase"] = str(
                selected_occurrence.get("occurrence_phase")
                or selected_occurrence.get("occurrence_role")
                or ""
            ).strip().casefold() or None
            row["_semantic_occurrence_id"] = str(selected_occurrence.get("id") or "").strip() or None
        elif dimension == "proposal_status":
            row["_semantic_lifecycle_phase"] = "proposal"
        elif dimension == "execution_status":
            row["_semantic_lifecycle_phase"] = "execution"
        else:
            row["_semantic_lifecycle_phase"] = "project_current"

        row["_semantic_evidence_backed"] = bool(
            row.get("source_evidence_id")
            or row.get("source_claim_id")
            or row.get("is_human_confirmed")
        )

    for row in legacy:
        source_table = str(row.get("_legacy_source_table") or "").strip()
        role = str(row.get("_legacy_role") or "").strip()
        dimension = _outcome_dimension(row)

        if source_table == "memory_project_outcomes" or role == "project_outcome":
            row["_semantic_subject_kind"] = "project"
            row["_semantic_subject_key"] = f"project:{project_id}"
            row["_semantic_subject_name"] = None
            row["_semantic_subject_binding"] = "legacy_project_outcome"
        elif source_table == "memory_item_outcomes":
            item_id = str(row.get("item_id") or "").strip()
            entity_ids = legacy_item_to_entities.get(item_id, set())
            if len(entity_ids) == 1:
                entity_id = next(iter(entity_ids))
                solution = entity_to_solution.get(entity_id) or {}
                row["_semantic_subject_kind"] = "solution"
                row["_semantic_subject_key"] = f"solution:{entity_id}"
                row["_semantic_subject_name"] = str(solution.get("name") or "").strip() or None
                row["_semantic_solution_instance_id"] = str(solution.get("id") or "").strip() or None
                row["_semantic_subject_binding"] = "legacy_item_id_to_solution_legacy_source_id"
            elif len(entity_ids) > 1:
                row["_semantic_subject_kind"] = "ambiguous_solution"
                row["_semantic_subject_key"] = None
                row["_semantic_subject_name"] = None
                row["_semantic_subject_binding"] = "legacy_item_maps_to_multiple_solution_entities"
            else:
                row["_semantic_subject_kind"] = "legacy_item"
                row["_semantic_subject_key"] = f"legacy_item:{item_id}" if item_id else None
                row["_semantic_subject_name"] = None
                row["_semantic_subject_binding"] = "legacy_item_without_domain_identity_binding"
        else:
            row["_semantic_subject_kind"] = "unknown"
            row["_semantic_subject_key"] = None
            row["_semantic_subject_name"] = None
            row["_semantic_subject_binding"] = "unknown_legacy_outcome_subject"

        material_feedback = _material_feedback(row)
        row["_semantic_material_feedback"] = material_feedback
        if material_feedback:
            row["_semantic_lifecycle_phase"] = "feedback"
        elif dimension == "execution_status":
            row["_semantic_lifecycle_phase"] = "execution"
        elif dimension == "proposal_status":
            row["_semantic_lifecycle_phase"] = "proposal_or_result"
        else:
            row["_semantic_lifecycle_phase"] = "project_result"

        # Legacy labels are preserved as provenance signals, never promoted to
        # evidence-backed truth by this binder.
        row["_semantic_evidence_backed"] = bool(row.get("_legacy_human_confirmed"))

    return domain, legacy
