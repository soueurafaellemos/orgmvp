from __future__ import annotations

"""NAVE V28.7.2B — conservative evidence-backed semantic relation planner."""

import hashlib
import json
from typing import Any, Mapping, Sequence
from uuid import NAMESPACE_URL, uuid5


def _sha(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _stable_uuid(label: str) -> str:
    return str(uuid5(NAMESPACE_URL, label))


def _relation(
    project_id: str,
    source_entity_id: str,
    relation_type: str,
    target_entity_id: str,
    evidence_unit_ids: Sequence[str],
    *,
    relation_kind: str = "fact",
    confidence: float,
    authority_score: float,
    attributes: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    evidence_ids = sorted(dict.fromkeys(str(v) for v in evidence_unit_ids if v))
    relation_hash = _sha({
        "project_id": project_id,
        "source": source_entity_id,
        "type": relation_type,
        "target": target_entity_id,
        "kind": relation_kind,
    })
    return {
        "id": _stable_uuid("nave:v2872b:relation:" + relation_hash),
        "source_entity_id": source_entity_id,
        "relation_type": relation_type,
        "target_entity_id": target_entity_id,
        "scope_entity_id": None,
        "relation_kind": relation_kind,
        "strength": None,
        "confidence": confidence,
        "authority_score": authority_score,
        "status": "active",
        "attributes": {"normalized_by": "V28.7.2B", **dict(attributes or {})},
        "relation_hash": relation_hash,
        "evidence_unit_ids": evidence_ids,
        "evidence_weight": confidence,
    }


def _evidence_ids(row: Mapping[str, Any]) -> list[str]:
    values = row.get("evidence_ids") if isinstance(row.get("evidence_ids"), list) else []
    if row.get("source_evidence_id"):
        values = [*values, str(row.get("source_evidence_id"))]
    return list(dict.fromkeys(str(v) for v in values if v))




def _source_asset_ids(row: Mapping[str, Any]) -> list[str]:
    attrs = row.get("attributes") if isinstance(row.get("attributes"), Mapping) else {}
    values = attrs.get("source_asset_ids") if isinstance(attrs.get("source_asset_ids"), list) else []
    return list(dict.fromkeys(str(v) for v in values if v))

def plan_core_semantic_relations(
    project_id: str,
    *,
    strategy_elements: Sequence[Mapping[str, Any]],
    creative_platforms: Sequence[Mapping[str, Any]],
    creative_elements: Sequence[Mapping[str, Any]],
    experience_architectures: Sequence[Mapping[str, Any]],
    journey_moments: Sequence[Mapping[str, Any]],
    solution_occurrences: Sequence[Mapping[str, Any]] = (),
    solution_instances: Sequence[Mapping[str, Any]] = (),
    context_elements: Sequence[Mapping[str, Any]] = (),
    requirements: Sequence[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Create facts only from shared evidence; cross-evidence structure is marked inference."""
    relations: list[dict[str, Any]] = []

    strategy_by_ev: dict[str, list[Mapping[str, Any]]] = {}
    creative_by_ev: dict[str, list[Mapping[str, Any]]] = {}
    experience_by_ev: dict[str, list[Mapping[str, Any]]] = {}
    journey_by_ev: dict[str, list[Mapping[str, Any]]] = {}
    for row in strategy_elements:
        for ev in _evidence_ids(row):
            strategy_by_ev.setdefault(ev, []).append(row)
    for row in creative_platforms:
        for ev in _evidence_ids(row):
            creative_by_ev.setdefault(ev, []).append(row)
    for row in experience_architectures:
        for ev in _evidence_ids(row):
            experience_by_ev.setdefault(ev, []).append(row)
    for row in journey_moments:
        for ev in _evidence_ids(row):
            journey_by_ev.setdefault(ev, []).append(row)

    # Context / Requirement -> informs -> Strategy only with shared evidence.
    context_by_ev: dict[str, list[Mapping[str, Any]]] = {}
    for row in context_elements:
        if row.get("source_evidence_id") and row.get("entity_id"):
            context_by_ev.setdefault(str(row["source_evidence_id"]), []).append(row)
    requirement_by_ev: dict[str, list[Mapping[str, Any]]] = {}
    for req in requirements:
        for ev in req.get("evidence_ids") or []:
            requirement_by_ev.setdefault(str(ev), []).append(req)
    for ev, strategies in strategy_by_ev.items():
        for strategy in strategies:
            for context in context_by_ev.get(ev, []):
                relations.append(_relation(
                    project_id, str(context["entity_id"]), "informs", str(strategy["entity_id"]), [ev],
                    confidence=0.97, authority_score=0.88,
                    attributes={"basis": "shared_evidence", "source_domain": "context"},
                ))
            for req in requirement_by_ev.get(ev, []):
                if req.get("entity_id"):
                    relations.append(_relation(
                        project_id, str(req["entity_id"]), "informs", str(strategy["entity_id"]), [ev],
                        confidence=0.96, authority_score=0.86,
                        attributes={"basis": "shared_evidence", "source_domain": "requirement"},
                    ))

    # Strategy -> expressed_by -> Creative Platform only with shared evidence.
    for ev in set(strategy_by_ev) & set(creative_by_ev):
        for strategy in strategy_by_ev[ev]:
            for creative in creative_by_ev[ev]:
                relations.append(_relation(
                    project_id, str(strategy["entity_id"]), "expressed_by", str(creative["entity_id"]), [ev],
                    confidence=0.97, authority_score=0.86,
                    attributes={"basis": "shared_evidence"},
                ))

    # Creative -> orchestrated_as -> Experience only with shared evidence.
    for ev in set(creative_by_ev) & set(experience_by_ev):
        for creative in creative_by_ev[ev]:
            for experience in experience_by_ev[ev]:
                relations.append(_relation(
                    project_id, str(creative["entity_id"]), "orchestrated_as", str(experience["entity_id"]), [ev],
                    confidence=0.97, authority_score=0.86,
                    attributes={"basis": "shared_evidence"},
                ))

    # Creative Platform contains its typed creative elements. Shared evidence is a fact;
    # a unique same-source platform association is an explicit inference, never disguised as fact.
    platform_by_id = {str(row.get("id")): row for row in creative_platforms if row.get("id")}
    for element in creative_elements:
        platform = platform_by_id.get(str(element.get("platform_id") or ""))
        if not platform:
            continue
        shared = sorted(set(_evidence_ids(platform)) & set(_evidence_ids(element)))
        association_mode = str(element.get("platform_association_mode") or (element.get("attributes") or {}).get("platform_association_mode") or "source_explicit")
        if shared:
            relations.append(_relation(
                project_id, str(platform["entity_id"]), "contains", str(element["entity_id"]), shared,
                relation_kind="fact", confidence=0.99, authority_score=0.88,
                attributes={"basis": "shared_evidence", "containment": "platform_element"},
            ))
        elif association_mode == "evidence_synthesis":
            relations.append(_relation(
                project_id, str(platform["entity_id"]), "contains", str(element["entity_id"]),
                [*_evidence_ids(platform), *_evidence_ids(element)],
                relation_kind="inference", confidence=0.90, authority_score=0.74,
                attributes={"basis": "unique_same_source_creative_platform", "containment": "platform_element"},
            ))

    # If source pages separate Strategy and the one explicit Creative Platform, a same-source
    # link can exist as an explicit inference (never fact). Multiple routes stay ambiguous.
    if len(creative_platforms) == 1:
        creative = creative_platforms[0]
        creative_assets = set(_source_asset_ids(creative))
        for strategy in strategy_elements:
            shared_assets = creative_assets & set(_source_asset_ids(strategy))
            shared_evidence = set(_evidence_ids(creative)) & set(_evidence_ids(strategy))
            if shared_assets and not shared_evidence:
                relations.append(_relation(
                    project_id, str(strategy["entity_id"]), "expressed_by", str(creative["entity_id"]),
                    [*_evidence_ids(strategy), *_evidence_ids(creative)],
                    relation_kind="inference", confidence=0.88, authority_score=0.72,
                    attributes={"basis": "same_source_single_creative_platform", "source_asset_ids": sorted(shared_assets)},
                ))

    # Same conservative rule for a single Creative Platform and a single Experience
    # Architecture when they are explicit in the same source but on different Evidence Units.
    if len(creative_platforms) == 1 and len(experience_architectures) == 1:
        creative = creative_platforms[0]
        experience = experience_architectures[0]
        shared_assets = set(_source_asset_ids(creative)) & set(_source_asset_ids(experience))
        shared_evidence = set(_evidence_ids(creative)) & set(_evidence_ids(experience))
        if shared_assets and not shared_evidence:
            relations.append(_relation(
                project_id, str(creative["entity_id"]), "orchestrated_as", str(experience["entity_id"]),
                [*_evidence_ids(creative), *_evidence_ids(experience)],
                relation_kind="inference", confidence=0.86, authority_score=0.70,
                attributes={"basis": "same_source_single_platform_single_architecture", "source_asset_ids": sorted(shared_assets)},
            ))

    experience_by_id = {str(row.get("id")): row for row in experience_architectures if row.get("id")}
    # Experience contains Journey Moment. Shared evidence = fact. Unique-architecture
    # cross-evidence association remains explicitly inference and carries both evidence sets.
    for moment in journey_moments:
        architecture = experience_by_id.get(str(moment.get("architecture_id") or ""))
        if not architecture:
            continue
        shared = sorted(set(_evidence_ids(moment)) & set(_evidence_ids(architecture)))
        association_mode = str(moment.get("architecture_association_mode") or "source_explicit")
        if shared:
            relations.append(_relation(
                project_id, str(architecture["entity_id"]), "contains", str(moment["entity_id"]), shared,
                relation_kind="fact", confidence=0.99, authority_score=0.88,
                attributes={"basis": "shared_evidence", "containment": "architecture_moment"},
            ))
        elif association_mode == "evidence_synthesis":
            relations.append(_relation(
                project_id, str(architecture["entity_id"]), "contains", str(moment["entity_id"]),
                [*_evidence_ids(architecture), *_evidence_ids(moment)],
                relation_kind="inference", confidence=0.90, authority_score=0.74,
                attributes={"basis": "unique_explicit_architecture_plus_explicit_moment", "containment": "architecture_moment"},
            ))

    # Creative can govern a Journey Moment only when co-located in evidence.
    for ev in set(creative_by_ev) & set(journey_by_ev):
        for creative in creative_by_ev[ev]:
            for moment in journey_by_ev[ev]:
                relations.append(_relation(
                    project_id, str(creative["entity_id"]), "governs", str(moment["entity_id"]), [ev],
                    confidence=0.96, authority_score=0.84,
                    attributes={"basis": "shared_evidence"},
                ))

    # Journey Moment -> contains -> Solution only when the Solution has an occurrence in
    # exactly the same Evidence Unit. No source proximity shortcut is allowed.
    solution_by_id = {str(row.get("id")): row for row in solution_instances if row.get("id")}
    occurrence_by_ev: dict[str, list[Mapping[str, Any]]] = {}
    for occurrence in solution_occurrences:
        if occurrence.get("evidence_unit_id") and occurrence.get("solution_instance_id"):
            occurrence_by_ev.setdefault(str(occurrence["evidence_unit_id"]), []).append(occurrence)
    for ev, moments in journey_by_ev.items():
        for occurrence in occurrence_by_ev.get(ev, []):
            solution = solution_by_id.get(str(occurrence.get("solution_instance_id") or "")) or {}
            if not solution.get("entity_id"):
                continue
            for moment in moments:
                relations.append(_relation(
                    project_id, str(moment["entity_id"]), "contains", str(solution["entity_id"]), [ev],
                    confidence=0.95, authority_score=0.84,
                    attributes={"basis": "shared_evidence", "containment": "moment_solution"},
                ))

    # Deterministic dedupe by semantic relation identity. Evidence from duplicates is merged.
    merged: dict[str, dict[str, Any]] = {}
    for row in relations:
        existing = merged.get(row["relation_hash"])
        if existing is None:
            merged[row["relation_hash"]] = row
            continue
        existing["evidence_unit_ids"] = sorted(set(existing.get("evidence_unit_ids") or []) | set(row.get("evidence_unit_ids") or []))
        existing["confidence"] = max(float(existing.get("confidence") or 0), float(row.get("confidence") or 0))
        existing["authority_score"] = max(float(existing.get("authority_score") or 0), float(row.get("authority_score") or 0))
    return list(merged.values())
