from __future__ import annotations

"""NAVE V28.7.3B2.4.5 — Unified Residual Evidence Coverage Audit.

READ ONLY / diagnostic only.

B2.4.4 projects out clear non-response evidence (cover/title page, brief recap,
ambiguous Stories). After that gate JOVI retains only a small set of Legacy
response candidates without Current Domain aliases.

This phase asks the next narrow question:
Does the SAME retained proposal evidence materially support any Current Domain
requirement, even though the raw Domain Unified did not surface it?

No alias is created. No score is changed. No runtime consumer is changed.
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
from project_requirement_unified_evidence_role_shadow import (
    classify_response_evidence_role,
)

RESIDUAL_COVERAGE_VERSION = "V28.7.3B2.4.5"
MATCH_THRESHOLD = 0.38


@dataclass(frozen=True)
class ResidualCoverageAudit:
    project_id: str
    status: str
    retained_legacy_residual_count: int
    residual_with_domain_full_match_count: int
    residual_with_title_only_match_count: int
    residual_near_threshold_count: int
    residual_without_domain_coverage_count: int
    detail_rows: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": RESIDUAL_COVERAGE_VERSION,
            "project_id": self.project_id,
            "status": self.status,
            "retained_legacy_residual_count": self.retained_legacy_residual_count,
            "residual_with_domain_full_match_count":
                self.residual_with_domain_full_match_count,
            "residual_with_title_only_match_count":
                self.residual_with_title_only_match_count,
            "residual_near_threshold_count":
                self.residual_near_threshold_count,
            "residual_without_domain_coverage_count":
                self.residual_without_domain_coverage_count,
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


def _matcher_input(requirement: Mapping[str, Any]) -> str:
    return " ".join(
        str(requirement.get(key) or "")
        for key in ("title", "description", "source_quote", "requirement_type")
    ).strip()


def _production_pair_score(query: str, evidence_text: str) -> float:
    """Exact pair score used by the current Unified briefing matcher."""
    from project_intelligence_unified import _match_score, _tokens

    score = _match_score(query, evidence_text)
    qt = _tokens(query)
    et = _tokens(evidence_text)
    if qt and et:
        score = max(
            score,
            len(qt & et) / max(1, min(len(qt), 8)) * 0.85,
        )
    return min(score, 0.98)


def _candidate_class(
    *,
    full_score: float,
    title_score: float,
) -> str:
    if full_score >= MATCH_THRESHOLD:
        return "DOMAIN_FULL_INPUT_SUPPORTS_SAME_EVIDENCE"
    if title_score >= MATCH_THRESHOLD:
        return "TITLE_ONLY_SUPPORTS_SAME_EVIDENCE"
    if full_score >= 0.25 or title_score >= 0.25:
        return "NEAR_THRESHOLD_DOMAIN_CANDIDATE"
    return "WEAK_OR_NO_DOMAIN_COVERAGE"


def audit_residual_evidence_coverage(
    *,
    project_id: str,
    legacy_requirement_rows: Sequence[Mapping[str, Any]],
    domain_requirement_rows: Sequence[Mapping[str, Any]],
    legacy_unified: Mapping[str, Any],
    domain_unified: Mapping[str, Any],
    compatibility: Any,
    top_k: int = 10,
) -> ResidualCoverageAudit:
    legacy_idx = _req_index(legacy_requirement_rows)
    domain_idx = _req_index(domain_requirement_rows)
    legacy_matches = _match_index(legacy_unified)
    domain_matches = _match_index(domain_unified)
    legacy_to_domain, domain_to_legacy = compatibility_alias_maps(compatibility)

    residuals: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for legacy_id, match in legacy_matches.items():
        if legacy_id in legacy_to_domain:
            continue
        req = legacy_idx.get(legacy_id, {})
        role, _, _ = classify_response_evidence_role(req, match)
        if role == "retain_response_candidate":
            residuals.append((legacy_id, req, match))

    detail: list[dict[str, Any]] = []
    full_supported_residuals: set[str] = set()
    title_only_residuals: set[str] = set()
    near_residuals: set[str] = set()
    no_coverage_residuals: set[str] = set()

    for legacy_id, legacy_req, legacy_match in residuals:
        evidence = (
            legacy_match.get("evidence")
            if isinstance(legacy_match.get("evidence"), Mapping)
            else {}
        )
        evidence_text = str(evidence.get("text") or "")
        candidates: list[dict[str, Any]] = []

        for domain_id, domain_req in domain_idx.items():
            full_score = _production_pair_score(
                _matcher_input(domain_req),
                evidence_text,
            )
            title_score = _production_pair_score(
                str(domain_req.get("title") or ""),
                evidence_text,
            )
            candidate_class = _candidate_class(
                full_score=full_score,
                title_score=title_score,
            )
            current_domain_match = domain_matches.get(domain_id)
            current_evidence = (
                current_domain_match.get("evidence")
                if isinstance(current_domain_match, Mapping)
                and isinstance(current_domain_match.get("evidence"), Mapping)
                else {}
            )

            candidates.append({
                "legacy_requirement_id": legacy_id,
                "legacy_title": legacy_req.get("title"),
                "legacy_type": legacy_req.get("requirement_type"),
                "legacy_match_score": legacy_match.get("score"),
                "legacy_evidence_id": evidence.get("evidence_id"),
                "legacy_evidence_source": evidence.get("source_name"),
                "legacy_evidence_locator": evidence.get("locator_text"),
                "legacy_evidence_text": evidence_text,
                "domain_requirement_id": domain_id,
                "domain_title": domain_req.get("title"),
                "domain_type": domain_req.get("requirement_type"),
                "domain_truth_state": domain_req.get("truth_state"),
                "domain_legacy_source_id": domain_req.get("legacy_source_id"),
                "domain_already_structurally_bound":
                    bool(domain_to_legacy.get(domain_id)),
                "same_evidence_full_score": round(full_score, 4),
                "same_evidence_title_only_score": round(title_score, 4),
                "candidate_class": candidate_class,
                "domain_current_unified_match":
                    current_domain_match is not None,
                "domain_current_match_score":
                    current_domain_match.get("score")
                    if isinstance(current_domain_match, Mapping)
                    else None,
                "domain_current_evidence_id":
                    current_evidence.get("evidence_id"),
                "domain_current_evidence_locator":
                    current_evidence.get("locator_text"),
            })

        candidates.sort(
            key=lambda row: (
                -max(
                    float(row["same_evidence_full_score"]),
                    float(row["same_evidence_title_only_score"]),
                ),
                -float(row["same_evidence_full_score"]),
                str(row.get("domain_title") or "").casefold(),
                str(row.get("domain_requirement_id") or ""),
            )
        )
        top = candidates[: max(1, int(top_k))]
        for rank, row in enumerate(top, start=1):
            row["candidate_rank"] = rank
            detail.append(row)

        classes = {row["candidate_class"] for row in candidates}
        if "DOMAIN_FULL_INPUT_SUPPORTS_SAME_EVIDENCE" in classes:
            full_supported_residuals.add(legacy_id)
        elif "TITLE_ONLY_SUPPORTS_SAME_EVIDENCE" in classes:
            title_only_residuals.add(legacy_id)
        elif "NEAR_THRESHOLD_DOMAIN_CANDIDATE" in classes:
            near_residuals.add(legacy_id)
        else:
            no_coverage_residuals.add(legacy_id)

    if not residuals:
        status = "PASS_NO_RETAINED_RESIDUALS"
    elif full_supported_residuals:
        status = "DOMAIN_COVERAGE_EXISTS_RECONCILIATION_REQUIRED"
    elif title_only_residuals:
        status = "TITLE_CANONICALIZATION_HYPOTHESIS"
    elif near_residuals:
        status = "DOMAIN_NEAR_COVERAGE_REVIEW"
    else:
        status = "DOMAIN_COVERAGE_GAP_REVIEW"

    detail.sort(
        key=lambda row: (
            str(row.get("legacy_title") or "").casefold(),
            int(row.get("candidate_rank") or 999),
        )
    )

    return ResidualCoverageAudit(
        project_id=str(project_id),
        status=status,
        retained_legacy_residual_count=len(residuals),
        residual_with_domain_full_match_count=len(full_supported_residuals),
        residual_with_title_only_match_count=len(title_only_residuals),
        residual_near_threshold_count=len(near_residuals),
        residual_without_domain_coverage_count=len(no_coverage_residuals),
        detail_rows=tuple(detail),
    )


def _rows(response: Any) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in (getattr(response, "data", None) or [])
        if isinstance(row, Mapping)
    ]


def run_residual_evidence_coverage_audit(
    client: Any,
    *,
    project_id: str,
) -> ResidualCoverageAudit:
    from project_intelligence_unified import build_unified_project_snapshot
    from project_workspace_db import fetch_project_workspace_snapshot

    compatibility = load_requirement_compatibility(
        client,
        project_id=project_id,
    )
    if not compatibility.pass_data_bridge:
        raise RuntimeError(
            "B2.4.5 BLOCKED: B2.1 compatibility is not PASS_DATA_BRIDGE."
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

    return audit_residual_evidence_coverage(
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
        legacy_unified=legacy_unified,
        domain_unified=domain_unified,
        compatibility=compatibility,
    )
