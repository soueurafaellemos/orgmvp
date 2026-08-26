from __future__ import annotations

"""NAVE V28.7.3B2.2 — Requirements Relational Consumer Shadow.

Runs the current Legacy workspace intelligence and a parallel Domain-ID shadow
from the same source snapshot, then compares relationship semantics.

This module is read-only. It never persists intelligence, changes read_mode,
promotes domain_primary, or writes Truth/adherence.
"""

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from project_requirement_compatibility import (
    RequirementCompatibilityReport,
    compatibility_alias_maps,
    load_requirement_compatibility,
)


RELATIONAL_SHADOW_VERSION = "V28.7.3B2.2"
_CURRENT_TRUTH = {"verified", "human_confirmed"}


@dataclass(frozen=True)
class RelationalShadowResult:
    project_id: str
    status: str
    hard_blockers: tuple[str, ...]
    observations: tuple[str, ...]
    legacy_requirement_count: int
    domain_requirement_count: int
    legacy_active_link_count: int
    domain_active_link_count: int
    matrix_row_count_legacy: int
    matrix_row_count_domain: int
    matrix_briefing_drift_count: int
    orphan_domain_link_count: int
    active_link_signature_drift: bool
    legacy_unified_match_count: int
    domain_unified_match_count: int
    mapped_legacy_unified_match_count: int
    mapped_legacy_matches_missing_in_domain: tuple[str, ...]
    domain_unified_additions: tuple[str, ...]
    legacy_unmapped_unified_matches: tuple[str, ...]
    legacy_gap_count: int
    domain_gap_count: int
    legacy_unconsolidated_count: int
    domain_unconsolidated_count: int
    matrix_drift_detail: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": RELATIONAL_SHADOW_VERSION,
            "project_id": self.project_id,
            "status": self.status,
            "hard_blockers": list(self.hard_blockers),
            "observations": list(self.observations),
            "legacy_requirement_count": self.legacy_requirement_count,
            "domain_requirement_count": self.domain_requirement_count,
            "legacy_active_link_count": self.legacy_active_link_count,
            "domain_active_link_count": self.domain_active_link_count,
            "matrix_row_count_legacy": self.matrix_row_count_legacy,
            "matrix_row_count_domain": self.matrix_row_count_domain,
            "matrix_briefing_drift_count": self.matrix_briefing_drift_count,
            "orphan_domain_link_count": self.orphan_domain_link_count,
            "active_link_signature_drift": self.active_link_signature_drift,
            "legacy_unified_match_count": self.legacy_unified_match_count,
            "domain_unified_match_count": self.domain_unified_match_count,
            "mapped_legacy_unified_match_count": self.mapped_legacy_unified_match_count,
            "mapped_legacy_matches_missing_in_domain": list(
                self.mapped_legacy_matches_missing_in_domain
            ),
            "domain_unified_additions": list(self.domain_unified_additions),
            "legacy_unmapped_unified_matches": list(
                self.legacy_unmapped_unified_matches
            ),
            "legacy_gap_count": self.legacy_gap_count,
            "domain_gap_count": self.domain_gap_count,
            "legacy_unconsolidated_count": self.legacy_unconsolidated_count,
            "domain_unconsolidated_count": self.domain_unconsolidated_count,
            "matrix_drift_detail": list(self.matrix_drift_detail),
        }


def _text(row: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _active_link(row: Mapping[str, Any]) -> bool:
    return (_text(row, "link_status") or "suggested").casefold() != "rejected"


def _json_attrs(row: Mapping[str, Any]) -> Mapping[str, Any]:
    value = row.get("attributes")
    return value if isinstance(value, Mapping) else {}


def _normalise_domain_requirement(row: Mapping[str, Any]) -> dict[str, Any] | None:
    """Use the approved B1 Domain adapter as the canonical shadow shape."""
    from project_domain_requirement_consumer import adapt_domain_requirements

    truth = (_text(row, "truth_state", "verification_state") or "").casefold()
    requirement_id = _text(row, "id", "requirement_id", "resolved_domain_id")
    if not requirement_id or truth not in _CURRENT_TRUTH:
        return None

    adapted_rows = adapt_domain_requirements([row])
    if not adapted_rows:
        return None
    adapted = adapted_rows[0]

    title = str(adapted.get("title") or "").strip() or "Demanda"
    description = str(adapted.get("description") or "").strip() or title
    source_quote = str(adapted.get("source_excerpt") or "").strip() or None

    return {
        "id": str(adapted.get("stable_key") or requirement_id),
        "project_id": _text(row, "project_id"),
        "entity_id": _text(row, "entity_id"),
        "legacy_source_id": _text(row, "legacy_source_id"),
        "title": title,
        "description": description,
        "original_text": description,
        "source_quote": source_quote,
        "requirement_type": str(adapted.get("requirement_type") or "other"),
        "mandatory": adapted.get("mandatory"),
        "priority": adapted.get("priority") or "not_informed",
        "adherence_status": "not_assessed",
        "adherence_evidence": None,
        "adherence_notes": None,
        "truth_state": str(adapted.get("truth_status") or truth),
        "_identity_source": "current_domain_truth",
        "_domain_adapter_parity": "V28.7.3B2.4.2",
    }


def build_domain_relational_shadow_snapshot(
    legacy_snapshot: Mapping[str, Any],
    *,
    domain_requirement_rows: Sequence[Mapping[str, Any]],
    compatibility: RequirementCompatibilityReport,
) -> dict[str, Any]:
    """Copy the workspace snapshot and replace only requirement identity inputs.

    Legacy business/UI snapshot remains untouched outside this copied shadow.
    """
    if not compatibility.pass_data_bridge:
        raise RuntimeError("B2.2 BLOCKED: compatibility bridge is not PASS_DATA_BRIDGE")

    shadow = deepcopy(dict(legacy_snapshot))
    # Deterministic comparison only: do not reuse a persisted semantic synthesis.
    shadow["intelligence_snapshots"] = []
    shadow.pop("unified_intelligence", None)

    domain_requirements = []
    for row in domain_requirement_rows:
        normalised = _normalise_domain_requirement(row)
        if normalised:
            domain_requirements.append(normalised)
    shadow["briefing_requirements"] = domain_requirements

    resolved_by_link = {
        link.legacy_link_id: link
        for link in compatibility.links
    }

    translated_links: list[dict[str, Any]] = []
    for original in legacy_snapshot.get("briefing_links", []) or []:
        row = dict(original)
        if not _active_link(row):
            translated_links.append(row)
            continue

        link_id = _text(row, "id")
        resolved = resolved_by_link.get(link_id or "")
        if resolved is None:
            # Keep it visible to the comparator as orphan, never invent a mapping.
            row["_compatibility_unresolved"] = True
            translated_links.append(row)
            continue

        row["legacy_requirement_id"] = resolved.legacy_requirement_id
        row["requirement_id"] = resolved.domain_requirement_id
        row["_compatibility_version"] = RELATIONAL_SHADOW_VERSION
        row["_identity_source"] = "domain_via_structural_bridge"
        translated_links.append(row)

    shadow["briefing_links"] = translated_links
    return shadow


def _matrix_by_item(intelligence: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(row.get("item_id") or ""): row
        for row in intelligence.get("matrix", []) or []
        if row.get("item_id")
    }


def _link_signature(
    snapshot: Mapping[str, Any],
    *,
    legacy_to_domain: Mapping[str, str] | None = None,
) -> set[tuple[str, str, str, str, str]]:
    signatures: set[tuple[str, str, str, str, str]] = set()
    for row in snapshot.get("briefing_links", []) or []:
        if not _active_link(row):
            continue
        requirement_id = str(row.get("requirement_id") or "")
        if legacy_to_domain is not None:
            requirement_id = str(legacy_to_domain.get(requirement_id) or "")
        signatures.add((
            requirement_id,
            str(row.get("memory_item_id") or ""),
            str(row.get("link_status") or "suggested"),
            str(row.get("adherence_status") or "not_assessed"),
            str(row.get("evidence") or row.get("adherence_evidence") or ""),
        ))
    return signatures


def _unified_match_ids(intelligence: Mapping[str, Any]) -> set[str]:
    unified = intelligence.get("unified")
    if not isinstance(unified, Mapping):
        unified = intelligence.get("unified_intelligence")
    if not isinstance(unified, Mapping):
        return set()
    return {
        str(row.get("requirement_id") or "")
        for row in unified.get("briefing_matches", []) or []
        if row.get("requirement_id")
    }


def compare_relational_shadow_outputs(
    *,
    project_id: str,
    legacy_snapshot: Mapping[str, Any],
    domain_shadow_snapshot: Mapping[str, Any],
    legacy_intelligence: Mapping[str, Any],
    domain_intelligence: Mapping[str, Any],
    compatibility: RequirementCompatibilityReport,
) -> RelationalShadowResult:
    legacy_to_domain, _ = compatibility_alias_maps(compatibility)
    blockers: list[str] = []
    observations: list[str] = []

    if not compatibility.pass_data_bridge:
        blockers.append("COMPATIBILITY_NOT_PASS_DATA_BRIDGE")

    legacy_active = [
        row for row in legacy_snapshot.get("briefing_links", []) or []
        if _active_link(row)
    ]
    domain_active = [
        row for row in domain_shadow_snapshot.get("briefing_links", []) or []
        if _active_link(row)
    ]

    legacy_signature = _link_signature(
        legacy_snapshot,
        legacy_to_domain=legacy_to_domain,
    )
    domain_signature = _link_signature(domain_shadow_snapshot)
    active_signature_drift = legacy_signature != domain_signature
    if active_signature_drift:
        blockers.append("ACTIVE_LINK_SIGNATURE_DRIFT")

    domain_ids = {
        str(row.get("id") or "")
        for row in domain_shadow_snapshot.get("briefing_requirements", []) or []
        if row.get("id")
    }
    item_ids = {
        str(row.get("id") or "")
        for row in domain_shadow_snapshot.get("memory_items", []) or []
        if row.get("id")
    }
    orphan_domain_links = [
        row for row in domain_active
        if str(row.get("requirement_id") or "") not in domain_ids
        or str(row.get("memory_item_id") or "") not in item_ids
    ]
    if orphan_domain_links:
        blockers.append("ORPHAN_DOMAIN_LINK")

    legacy_matrix = _matrix_by_item(legacy_intelligence)
    domain_matrix = _matrix_by_item(domain_intelligence)
    matrix_drift: list[dict[str, Any]] = []

    if set(legacy_matrix) != set(domain_matrix):
        blockers.append("MATRIX_ITEM_CARDINALITY_DRIFT")

    for item_id in sorted(set(legacy_matrix) | set(domain_matrix)):
        legacy_row = legacy_matrix.get(item_id) or {}
        domain_row = domain_matrix.get(item_id) or {}
        legacy_briefing = str(legacy_row.get("Briefing") or "")
        domain_briefing = str(domain_row.get("Briefing") or "")
        if legacy_briefing != domain_briefing:
            matrix_drift.append({
                "item_id": item_id,
                "item_title": legacy_row.get("Item apresentado")
                    or domain_row.get("Item apresentado"),
                "legacy_briefing": legacy_briefing,
                "domain_briefing": domain_briefing,
            })
    if matrix_drift:
        blockers.append("MATRIX_BRIEFING_RELATION_DRIFT")

    legacy_matches = _unified_match_ids(legacy_intelligence)
    domain_matches = _unified_match_ids(domain_intelligence)
    translated_legacy_matches = {
        legacy_to_domain[legacy_id]
        for legacy_id in legacy_matches
        if legacy_id in legacy_to_domain
    }
    legacy_unmapped_matches = {
        legacy_id for legacy_id in legacy_matches
        if legacy_id not in legacy_to_domain
    }
    mapped_missing = translated_legacy_matches - domain_matches
    domain_additions = domain_matches - translated_legacy_matches

    if mapped_missing:
        observations.append(
            "MAPPED_LEGACY_UNIFIED_MATCH_NOT_REPRODUCED_IN_DOMAIN"
        )
    if domain_additions:
        observations.append("DOMAIN_UNIFIED_MATCH_ADDITIONS")
    if legacy_unmapped_matches:
        observations.append("LEGACY_UNIFIED_MATCH_WITHOUT_DOMAIN_ALIAS")

    legacy_disc = legacy_intelligence.get("discrepancies") or {}
    domain_disc = domain_intelligence.get("discrepancies") or {}
    legacy_gap_count = len(legacy_disc.get("briefing_gaps") or [])
    domain_gap_count = len(domain_disc.get("briefing_gaps") or [])
    legacy_unc_count = len(legacy_disc.get("briefing_evidence_unconsolidated") or [])
    domain_unc_count = len(domain_disc.get("briefing_evidence_unconsolidated") or [])
    if (
        legacy_gap_count != domain_gap_count
        or legacy_unc_count != domain_unc_count
    ):
        observations.append("EXPECTED_REQUIREMENT_CARDINALITY_EFFECT")

    status = "BLOCKED" if blockers else (
        "PASS_WITH_OBSERVATION" if observations else "PASS"
    )

    return RelationalShadowResult(
        project_id=str(project_id),
        status=status,
        hard_blockers=tuple(sorted(set(blockers))),
        observations=tuple(sorted(set(observations))),
        legacy_requirement_count=len(legacy_snapshot.get("briefing_requirements", []) or []),
        domain_requirement_count=len(domain_shadow_snapshot.get("briefing_requirements", []) or []),
        legacy_active_link_count=len(legacy_active),
        domain_active_link_count=len(domain_active),
        matrix_row_count_legacy=len(legacy_matrix),
        matrix_row_count_domain=len(domain_matrix),
        matrix_briefing_drift_count=len(matrix_drift),
        orphan_domain_link_count=len(orphan_domain_links),
        active_link_signature_drift=active_signature_drift,
        legacy_unified_match_count=len(legacy_matches),
        domain_unified_match_count=len(domain_matches),
        mapped_legacy_unified_match_count=len(translated_legacy_matches),
        mapped_legacy_matches_missing_in_domain=tuple(sorted(mapped_missing)),
        domain_unified_additions=tuple(sorted(domain_additions)),
        legacy_unmapped_unified_matches=tuple(sorted(legacy_unmapped_matches)),
        legacy_gap_count=legacy_gap_count,
        domain_gap_count=domain_gap_count,
        legacy_unconsolidated_count=legacy_unc_count,
        domain_unconsolidated_count=domain_unc_count,
        matrix_drift_detail=tuple(matrix_drift),
    )


def _rows(response: Any) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in (getattr(response, "data", None) or [])
        if isinstance(row, Mapping)
    ]


def run_relational_consumer_shadow(
    client: Any,
    *,
    project_id: str,
) -> tuple[RelationalShadowResult, dict[str, Any], dict[str, Any]]:
    """Execute Legacy + parallel Domain-ID workspace intelligence in memory."""
    from project_workspace_db import fetch_project_workspace_snapshot
    from project_workspace_intelligence import build_project_intelligence

    compatibility = load_requirement_compatibility(
        client,
        project_id=project_id,
    )
    if not compatibility.pass_data_bridge:
        raise RuntimeError("B2.2 BLOCKED: compatibility bridge is not PASS_DATA_BRIDGE")

    domain_rows = _rows(
        client.table("project_requirement_truth_status")
        .select("*")
        .eq("project_id", project_id)
        .execute()
    )

    source_snapshot = fetch_project_workspace_snapshot(
        client,
        project_id=project_id,
    )

    legacy_snapshot = deepcopy(source_snapshot)
    legacy_snapshot["intelligence_snapshots"] = []
    legacy_snapshot.pop("unified_intelligence", None)

    domain_shadow_snapshot = build_domain_relational_shadow_snapshot(
        source_snapshot,
        domain_requirement_rows=domain_rows,
        compatibility=compatibility,
    )

    legacy_intelligence = build_project_intelligence(legacy_snapshot)
    domain_intelligence = build_project_intelligence(domain_shadow_snapshot)

    result = compare_relational_shadow_outputs(
        project_id=project_id,
        legacy_snapshot=legacy_snapshot,
        domain_shadow_snapshot=domain_shadow_snapshot,
        legacy_intelligence=legacy_intelligence,
        domain_intelligence=domain_intelligence,
        compatibility=compatibility,
    )
    return result, legacy_intelligence, domain_intelligence
