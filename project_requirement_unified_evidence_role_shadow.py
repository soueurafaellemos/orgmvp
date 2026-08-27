from __future__ import annotations

"""NAVE V28.7.3B2.4.4 — Unified Evidence-Role Gate Shadow.

READ ONLY / diagnostic only.

Purpose:
- classify every CURRENT Unified briefing match by the role of its evidence;
- project a conservative "response evidence" gate in memory;
- compare Legacy vs Current Domain AFTER the projected gate;
- never alter the production matcher, Truth, aliases, read_mode, canaries,
  persisted Unified, or consumer output.

The core semantic distinction is:
    requirement restatement / title-page mention != proposal response.

B2.4.4 is still a shadow. It does not enforce this rule in production.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from project_requirement_compatibility import load_requirement_compatibility
from project_requirement_relational_shadow import (
    build_domain_relational_shadow_snapshot,
)
from project_requirement_unified_reconciliation import (
    reconcile_unified_requirement_sets,
)
from project_requirement_unified_semantic_audit import (
    _evidence_quality_signals,
)

EVIDENCE_ROLE_SHADOW_VERSION = "V28.7.3B2.4.4"


@dataclass(frozen=True)
class EvidenceRoleShadowResult:
    project_id: str
    status: str
    raw_legacy_match_count: int
    raw_domain_match_count: int
    projected_legacy_match_count: int
    projected_domain_match_count: int
    excluded_legacy_count: int
    excluded_domain_count: int
    projected_mapped_missing_count: int
    projected_legacy_without_domain_alias_count: int
    projected_domain_without_legacy_alias_count: int
    projected_mapped_both_count: int
    detail_rows: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": EVIDENCE_ROLE_SHADOW_VERSION,
            "project_id": self.project_id,
            "status": self.status,
            "raw_legacy_match_count": self.raw_legacy_match_count,
            "raw_domain_match_count": self.raw_domain_match_count,
            "projected_legacy_match_count": self.projected_legacy_match_count,
            "projected_domain_match_count": self.projected_domain_match_count,
            "excluded_legacy_count": self.excluded_legacy_count,
            "excluded_domain_count": self.excluded_domain_count,
            "projected_mapped_missing_count": self.projected_mapped_missing_count,
            "projected_legacy_without_domain_alias_count":
                self.projected_legacy_without_domain_alias_count,
            "projected_domain_without_legacy_alias_count":
                self.projected_domain_without_legacy_alias_count,
            "projected_mapped_both_count": self.projected_mapped_both_count,
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


def _match_rows(unified: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in (unified.get("briefing_matches") or [])
        if isinstance(row, Mapping) and row.get("requirement_id")
    ]


def classify_response_evidence_role(
    requirement: Mapping[str, Any],
    match: Mapping[str, Any],
) -> tuple[str, tuple[str, ...], str]:
    """Project a conservative evidence role.

    This phase intentionally treats explicit brief recaps as NON-response evidence:
    repeating the requirement inside the proposal is not sufficient to prove that
    the proposal answered it.

    The classification is diagnostic-only in B2.4.4.
    """
    quality_status, flags = _evidence_quality_signals(requirement, match)
    flag_set = set(flags)

    if "COVER_OR_TITLE_PAGE_RISK" in flag_set:
        return (
            "exclude_non_response",
            flags,
            "cover_or_title_page_is_context_not_response",
        )

    if "AMBIGUOUS_STORIES_TERM_RISK" in flag_set:
        return (
            "exclude_non_response",
            flags,
            "ambiguous_lexical_mention_is_not_platform_response",
        )

    if "PLATFORM_MENTION_IN_RECAP_RISK" in flag_set:
        return (
            "exclude_non_response",
            flags,
            "platform_named_only_inside_brief_recap",
        )

    if "BRIEF_RECAP_RESTATEMENT_RISK" in flag_set:
        return (
            "exclude_non_response",
            flags,
            "brief_recap_restates_requirement_without_response_evidence",
        )

    return (
        "retain_response_candidate",
        flags,
        "no_high_confidence_non_response_signal",
    )


def _project_unified(
    unified: Mapping[str, Any],
    requirement_rows: Sequence[Mapping[str, Any]],
    *,
    side: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    idx = _req_index(requirement_rows)
    retained: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []

    for match in _match_rows(unified):
        requirement_id = str(match.get("requirement_id"))
        requirement = idx.get(requirement_id, {})
        role, flags, reason = classify_response_evidence_role(
            requirement,
            match,
        )
        evidence = (
            match.get("evidence")
            if isinstance(match.get("evidence"), Mapping)
            else {}
        )
        retained_flag = role == "retain_response_candidate"
        if retained_flag:
            retained.append(dict(match))

        audit_rows.append({
            "side": side,
            "requirement_id": requirement_id,
            "requirement_title": requirement.get("title"),
            "requirement_type": requirement.get("requirement_type"),
            "match_score": match.get("score"),
            "projected_role": role,
            "projected_retained": retained_flag,
            "projected_reason": reason,
            "quality_flags": " | ".join(flags),
            "evidence_id": evidence.get("evidence_id"),
            "evidence_source": evidence.get("source_name"),
            "evidence_locator": evidence.get("locator_text"),
            "evidence_text": evidence.get("text"),
        })

    projected = dict(unified)
    projected["briefing_matches"] = retained
    return projected, audit_rows


def build_evidence_role_shadow(
    *,
    project_id: str,
    legacy_requirement_rows: Sequence[Mapping[str, Any]],
    domain_requirement_rows: Sequence[Mapping[str, Any]],
    legacy_link_rows: Sequence[Mapping[str, Any]],
    legacy_unified: Mapping[str, Any],
    domain_unified: Mapping[str, Any],
    compatibility: Any,
) -> EvidenceRoleShadowResult:
    projected_legacy, legacy_detail = _project_unified(
        legacy_unified,
        legacy_requirement_rows,
        side="legacy",
    )
    projected_domain, domain_detail = _project_unified(
        domain_unified,
        domain_requirement_rows,
        side="domain",
    )

    projected_reconciliation = reconcile_unified_requirement_sets(
        project_id=project_id,
        legacy_requirement_rows=legacy_requirement_rows,
        domain_requirement_rows=domain_requirement_rows,
        legacy_link_rows=legacy_link_rows,
        legacy_unified=projected_legacy,
        domain_unified=projected_domain,
        compatibility=compatibility,
    )

    # A projected gate is not safe if it creates asymmetric loss of a Legacy match
    # that already has a governed structural Current Domain alias.
    if projected_reconciliation.mapped_legacy_missing_in_domain_count:
        status = "BLOCKED_PROJECTED_MAPPED_LOSS"
    elif (
        projected_reconciliation.legacy_match_without_domain_alias_count
        or projected_reconciliation.domain_match_without_legacy_alias_count
    ):
        status = "PROJECTED_RESIDUAL_SEMANTIC_REVIEW"
    elif projected_reconciliation.mapped_different_evidence_count:
        status = "PASS_WITH_EVIDENCE_OBSERVATION"
    else:
        status = "PASS_PROJECTED_PARITY"

    detail = legacy_detail + domain_detail
    detail.sort(
        key=lambda row: (
            str(row.get("side") or ""),
            str(row.get("requirement_title") or "").casefold(),
            str(row.get("requirement_id") or ""),
        )
    )

    raw_legacy = len(_match_rows(legacy_unified))
    raw_domain = len(_match_rows(domain_unified))
    proj_legacy = len(_match_rows(projected_legacy))
    proj_domain = len(_match_rows(projected_domain))

    return EvidenceRoleShadowResult(
        project_id=str(project_id),
        status=status,
        raw_legacy_match_count=raw_legacy,
        raw_domain_match_count=raw_domain,
        projected_legacy_match_count=proj_legacy,
        projected_domain_match_count=proj_domain,
        excluded_legacy_count=raw_legacy - proj_legacy,
        excluded_domain_count=raw_domain - proj_domain,
        projected_mapped_missing_count=
            projected_reconciliation.mapped_legacy_missing_in_domain_count,
        projected_legacy_without_domain_alias_count=
            projected_reconciliation.legacy_match_without_domain_alias_count,
        projected_domain_without_legacy_alias_count=
            projected_reconciliation.domain_match_without_legacy_alias_count,
        projected_mapped_both_count=
            projected_reconciliation.mapped_both_match_count,
        detail_rows=tuple(detail),
    )


def _rows(response: Any) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in (getattr(response, "data", None) or [])
        if isinstance(row, Mapping)
    ]


def run_evidence_role_shadow(
    client: Any,
    *,
    project_id: str,
) -> EvidenceRoleShadowResult:
    from project_intelligence_unified import build_unified_project_snapshot
    from project_workspace_db import fetch_project_workspace_snapshot

    compatibility = load_requirement_compatibility(
        client,
        project_id=project_id,
    )
    if not compatibility.pass_data_bridge:
        raise RuntimeError(
            "B2.4.4 BLOCKED: B2.1 compatibility is not PASS_DATA_BRIDGE."
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

    legacy_snapshot = dict(source_snapshot)
    legacy_snapshot.pop("unified_intelligence", None)
    domain_shadow.pop("unified_intelligence", None)

    legacy_unified = build_unified_project_snapshot(legacy_snapshot)
    domain_unified = build_unified_project_snapshot(domain_shadow)

    return build_evidence_role_shadow(
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
