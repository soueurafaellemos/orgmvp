from __future__ import annotations

"""NAVE V28.7.3B2.4 — Unified Requirement Set Reconciliation.

Diagnostic/read-only phase.

B2.2 proved the matrix relationship is preserved, but the Unified requirement
set differs between Legacy and Current Domain. This module identifies exactly
WHICH matched requirements account for the difference without changing the
matcher, identity graph, Truth, read_mode, canaries, or persisted intelligence.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from project_requirement_compatibility import (
    compatibility_alias_maps,
    load_requirement_compatibility,
)
from project_requirement_relational_shadow import (
    build_domain_relational_shadow_snapshot,
)


UNIFIED_RECONCILIATION_VERSION = "V28.7.3B2.4"


@dataclass(frozen=True)
class UnifiedRequirementReconciliation:
    project_id: str
    status: str
    hard_blockers: tuple[str, ...]
    observations: tuple[str, ...]
    legacy_requirement_count: int
    domain_requirement_count: int
    legacy_unified_match_count: int
    domain_unified_match_count: int
    mapped_legacy_match_count: int
    mapped_legacy_missing_in_domain_count: int
    legacy_match_without_domain_alias_count: int
    domain_match_without_legacy_alias_count: int
    mapped_both_match_count: int
    mapped_different_evidence_count: int
    detail_rows: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": UNIFIED_RECONCILIATION_VERSION,
            "project_id": self.project_id,
            "status": self.status,
            "hard_blockers": list(self.hard_blockers),
            "observations": list(self.observations),
            "legacy_requirement_count": self.legacy_requirement_count,
            "domain_requirement_count": self.domain_requirement_count,
            "legacy_unified_match_count": self.legacy_unified_match_count,
            "domain_unified_match_count": self.domain_unified_match_count,
            "mapped_legacy_match_count": self.mapped_legacy_match_count,
            "mapped_legacy_missing_in_domain_count":
                self.mapped_legacy_missing_in_domain_count,
            "legacy_match_without_domain_alias_count":
                self.legacy_match_without_domain_alias_count,
            "domain_match_without_legacy_alias_count":
                self.domain_match_without_legacy_alias_count,
            "mapped_both_match_count": self.mapped_both_match_count,
            "mapped_different_evidence_count":
                self.mapped_different_evidence_count,
            "detail_rows": list(self.detail_rows),
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


def _req_index(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for raw in rows:
        row = dict(raw)
        req_id = _text(row, "id", "requirement_id", "resolved_domain_id")
        if req_id:
            result[req_id] = row
    return result


def _match_index(unified: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for raw in unified.get("briefing_matches") or []:
        if not isinstance(raw, Mapping):
            continue
        row = dict(raw)
        req_id = _text(row, "requirement_id")
        if req_id:
            result[req_id] = row
    return result


def _evidence_fields(match: Mapping[str, Any] | None) -> dict[str, Any]:
    evidence = (
        match.get("evidence")
        if isinstance(match, Mapping) and isinstance(match.get("evidence"), Mapping)
        else {}
    )
    return {
        "score": match.get("score") if isinstance(match, Mapping) else None,
        "evidence_id": evidence.get("evidence_id"),
        "evidence_source": evidence.get("source_name"),
        "evidence_locator": evidence.get("locator_text"),
        "evidence_text": evidence.get("text"),
    }


def _active_link_counts(
    legacy_link_rows: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in legacy_link_rows:
        status = (_text(row, "link_status") or "suggested").casefold()
        if status == "rejected":
            continue
        req_id = _text(row, "requirement_id")
        if req_id:
            counts[req_id] = counts.get(req_id, 0) + 1
    return counts


def reconcile_unified_requirement_sets(
    *,
    project_id: str,
    legacy_requirement_rows: Sequence[Mapping[str, Any]],
    domain_requirement_rows: Sequence[Mapping[str, Any]],
    legacy_link_rows: Sequence[Mapping[str, Any]],
    legacy_unified: Mapping[str, Any],
    domain_unified: Mapping[str, Any],
    compatibility: Any,
) -> UnifiedRequirementReconciliation:
    """Classify the exact source of Legacy-vs-Domain Unified divergence.

    Important: structural aliases come exclusively from B2.1. No lexical mapping
    is created here.
    """
    blockers: list[str] = []
    observations: list[str] = []
    detail: list[dict[str, Any]] = []

    if not bool(getattr(compatibility, "pass_data_bridge", False)):
        blockers.append("COMPATIBILITY_NOT_PASS_DATA_BRIDGE")

    legacy_to_domain, domain_to_legacy = compatibility_alias_maps(compatibility)

    legacy_idx = _req_index(legacy_requirement_rows)
    domain_idx = _req_index(domain_requirement_rows)
    legacy_matches = _match_index(legacy_unified)
    domain_matches = _match_index(domain_unified)
    active_link_counts = _active_link_counts(legacy_link_rows)

    mapped_legacy_matches = {
        legacy_id: legacy_to_domain[legacy_id]
        for legacy_id in legacy_matches
        if legacy_id in legacy_to_domain
    }

    mapped_missing = {
        legacy_id: domain_id
        for legacy_id, domain_id in mapped_legacy_matches.items()
        if domain_id not in domain_matches
    }
    if mapped_missing:
        blockers.append("MAPPED_LEGACY_UNIFIED_MATCH_NOT_REPRODUCED_IN_DOMAIN")

    legacy_without_alias = sorted(
        legacy_id
        for legacy_id in legacy_matches
        if legacy_id not in legacy_to_domain
    )
    if legacy_without_alias:
        observations.append("LEGACY_MATCH_WITHOUT_CURRENT_DOMAIN_ALIAS")

    translated_legacy_match_ids = set(mapped_legacy_matches.values())
    domain_without_alias = sorted(
        domain_id
        for domain_id in domain_matches
        if not domain_to_legacy.get(domain_id)
    )
    if domain_without_alias:
        observations.append("DOMAIN_EVIDENCE_LED_MATCH_WITHOUT_LEGACY_ALIAS")

    mapped_both = sorted(
        (legacy_id, domain_id)
        for legacy_id, domain_id in mapped_legacy_matches.items()
        if domain_id in domain_matches
    )

    different_evidence = 0
    for legacy_id, domain_id in mapped_both:
        legacy_match = legacy_matches[legacy_id]
        domain_match = domain_matches[domain_id]
        legacy_ev = _evidence_fields(legacy_match)
        domain_ev = _evidence_fields(domain_match)
        evidence_same = (
            legacy_ev.get("evidence_id")
            and legacy_ev.get("evidence_id") == domain_ev.get("evidence_id")
        )
        if not evidence_same:
            different_evidence += 1
        legacy_req = legacy_idx.get(legacy_id, {})
        domain_req = domain_idx.get(domain_id, {})
        detail.append({
            "finding_type": (
                "mapped_both_match_same_evidence"
                if evidence_same
                else "mapped_both_match_different_evidence"
            ),
            "legacy_requirement_id": legacy_id,
            "legacy_title": legacy_req.get("title"),
            "legacy_type": legacy_req.get("requirement_type"),
            "legacy_mandatory": legacy_req.get("mandatory"),
            "legacy_priority": legacy_req.get("priority"),
            "legacy_active_link_count": active_link_counts.get(legacy_id, 0),
            "domain_requirement_id": domain_id,
            "domain_title": domain_req.get("title"),
            "domain_type": domain_req.get("requirement_type"),
            "domain_mandatory": domain_req.get("mandatory"),
            "domain_priority": domain_req.get("priority"),
            "domain_truth_state": domain_req.get("truth_state"),
            "legacy_score": legacy_ev.get("score"),
            "domain_score": domain_ev.get("score"),
            "legacy_evidence_id": legacy_ev.get("evidence_id"),
            "domain_evidence_id": domain_ev.get("evidence_id"),
            "legacy_evidence_source": legacy_ev.get("evidence_source"),
            "domain_evidence_source": domain_ev.get("evidence_source"),
            "legacy_evidence_locator": legacy_ev.get("evidence_locator"),
            "domain_evidence_locator": domain_ev.get("evidence_locator"),
            "legacy_evidence_text": legacy_ev.get("evidence_text"),
            "domain_evidence_text": domain_ev.get("evidence_text"),
        })

    if different_evidence:
        observations.append("MAPPED_MATCH_EVIDENCE_SELECTION_DIFFERS")

    for legacy_id, domain_id in sorted(mapped_missing.items()):
        legacy_req = legacy_idx.get(legacy_id, {})
        domain_req = domain_idx.get(domain_id, {})
        legacy_ev = _evidence_fields(legacy_matches.get(legacy_id))
        detail.append({
            "finding_type": "mapped_legacy_match_missing_in_domain",
            "legacy_requirement_id": legacy_id,
            "legacy_title": legacy_req.get("title"),
            "legacy_type": legacy_req.get("requirement_type"),
            "legacy_mandatory": legacy_req.get("mandatory"),
            "legacy_priority": legacy_req.get("priority"),
            "legacy_active_link_count": active_link_counts.get(legacy_id, 0),
            "domain_requirement_id": domain_id,
            "domain_title": domain_req.get("title"),
            "domain_type": domain_req.get("requirement_type"),
            "domain_mandatory": domain_req.get("mandatory"),
            "domain_priority": domain_req.get("priority"),
            "domain_truth_state": domain_req.get("truth_state"),
            "legacy_score": legacy_ev.get("score"),
            "domain_score": None,
            "legacy_evidence_id": legacy_ev.get("evidence_id"),
            "domain_evidence_id": None,
            "legacy_evidence_source": legacy_ev.get("evidence_source"),
            "domain_evidence_source": None,
            "legacy_evidence_locator": legacy_ev.get("evidence_locator"),
            "domain_evidence_locator": None,
            "legacy_evidence_text": legacy_ev.get("evidence_text"),
            "domain_evidence_text": None,
        })

    for legacy_id in legacy_without_alias:
        legacy_req = legacy_idx.get(legacy_id, {})
        legacy_ev = _evidence_fields(legacy_matches.get(legacy_id))
        detail.append({
            "finding_type": "legacy_match_without_current_domain_alias",
            "legacy_requirement_id": legacy_id,
            "legacy_title": legacy_req.get("title"),
            "legacy_description": legacy_req.get("description"),
            "legacy_type": legacy_req.get("requirement_type"),
            "legacy_mandatory": legacy_req.get("mandatory"),
            "legacy_priority": legacy_req.get("priority"),
            "legacy_adherence_status": legacy_req.get("adherence_status"),
            "legacy_active_link_count": active_link_counts.get(legacy_id, 0),
            "domain_requirement_id": None,
            "domain_title": None,
            "domain_truth_state": None,
            "legacy_score": legacy_ev.get("score"),
            "domain_score": None,
            "legacy_evidence_id": legacy_ev.get("evidence_id"),
            "domain_evidence_id": None,
            "legacy_evidence_source": legacy_ev.get("evidence_source"),
            "domain_evidence_source": None,
            "legacy_evidence_locator": legacy_ev.get("evidence_locator"),
            "domain_evidence_locator": None,
            "legacy_evidence_text": legacy_ev.get("evidence_text"),
            "domain_evidence_text": None,
        })

    for domain_id in domain_without_alias:
        domain_req = domain_idx.get(domain_id, {})
        domain_ev = _evidence_fields(domain_matches.get(domain_id))
        detail.append({
            "finding_type": "domain_match_without_legacy_alias",
            "legacy_requirement_id": None,
            "legacy_title": None,
            "legacy_active_link_count": 0,
            "domain_requirement_id": domain_id,
            "domain_title": domain_req.get("title"),
            "domain_description": domain_req.get("description"),
            "domain_type": domain_req.get("requirement_type"),
            "domain_mandatory": domain_req.get("mandatory"),
            "domain_priority": domain_req.get("priority"),
            "domain_truth_state": domain_req.get("truth_state"),
            "domain_has_current_evidence": domain_req.get("has_current_evidence"),
            "domain_has_direct_domain_evidence":
                domain_req.get("has_direct_domain_evidence"),
            "legacy_score": None,
            "domain_score": domain_ev.get("score"),
            "legacy_evidence_id": None,
            "domain_evidence_id": domain_ev.get("evidence_id"),
            "legacy_evidence_source": None,
            "domain_evidence_source": domain_ev.get("evidence_source"),
            "legacy_evidence_locator": None,
            "domain_evidence_locator": domain_ev.get("evidence_locator"),
            "legacy_evidence_text": None,
            "domain_evidence_text": domain_ev.get("evidence_text"),
        })

    if blockers:
        status = "BLOCKED_CALIBRATION"
    elif legacy_without_alias or domain_without_alias:
        status = "RECONCILIATION_REQUIRED"
    elif different_evidence:
        status = "PASS_WITH_OBSERVATION"
    else:
        status = "PASS"

    detail.sort(
        key=lambda row: (
            str(row.get("finding_type") or ""),
            str(row.get("legacy_title") or row.get("domain_title") or "").casefold(),
            str(row.get("legacy_requirement_id") or row.get("domain_requirement_id") or ""),
        )
    )

    return UnifiedRequirementReconciliation(
        project_id=str(project_id),
        status=status,
        hard_blockers=tuple(sorted(set(blockers))),
        observations=tuple(sorted(set(observations))),
        legacy_requirement_count=len(legacy_idx),
        domain_requirement_count=len(domain_idx),
        legacy_unified_match_count=len(legacy_matches),
        domain_unified_match_count=len(domain_matches),
        mapped_legacy_match_count=len(mapped_legacy_matches),
        mapped_legacy_missing_in_domain_count=len(mapped_missing),
        legacy_match_without_domain_alias_count=len(legacy_without_alias),
        domain_match_without_legacy_alias_count=len(domain_without_alias),
        mapped_both_match_count=len(mapped_both),
        mapped_different_evidence_count=different_evidence,
        detail_rows=tuple(detail),
    )


def _rows(response: Any) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in (getattr(response, "data", None) or [])
        if isinstance(row, Mapping)
    ]


def run_unified_requirement_reconciliation(
    client: Any,
    *,
    project_id: str,
) -> UnifiedRequirementReconciliation:
    """Run Legacy vs Domain Unified requirement-set analysis in memory only."""
    from project_intelligence_unified import build_unified_project_snapshot
    from project_workspace_db import fetch_project_workspace_snapshot

    compatibility = load_requirement_compatibility(
        client,
        project_id=project_id,
    )
    if not compatibility.pass_data_bridge:
        raise RuntimeError(
            "B2.4 BLOCKED: B2.1 compatibility is not PASS_DATA_BRIDGE."
        )

    source_snapshot = fetch_project_workspace_snapshot(
        client,
        project_id=project_id,
    )

    domain_rows = _rows(
        client.table("project_requirement_truth_status")
        .select("*")
        .eq("project_id", project_id)
        .execute()
    )

    domain_shadow = build_domain_relational_shadow_snapshot(
        source_snapshot,
        domain_requirement_rows=domain_rows,
        compatibility=compatibility,
    )

    # Force fresh deterministic Unified calculations in memory.
    legacy_snapshot = dict(source_snapshot)
    legacy_snapshot.pop("unified_intelligence", None)
    domain_shadow.pop("unified_intelligence", None)

    legacy_unified = build_unified_project_snapshot(legacy_snapshot)
    domain_unified = build_unified_project_snapshot(domain_shadow)

    return reconcile_unified_requirement_sets(
        project_id=project_id,
        legacy_requirement_rows=[
            dict(row)
            for row in (source_snapshot.get("briefing_requirements") or [])
            if isinstance(row, Mapping)
        ],
        domain_requirement_rows=[
            dict(row)
            for row in (domain_shadow.get("briefing_requirements") or [])
            if isinstance(row, Mapping)
        ],
        legacy_link_rows=[
            dict(row)
            for row in (source_snapshot.get("briefing_links") or [])
            if isinstance(row, Mapping)
        ],
        legacy_unified=legacy_unified,
        domain_unified=domain_unified,
        compatibility=compatibility,
    )
