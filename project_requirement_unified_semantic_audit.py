from __future__ import annotations

"""NAVE V28.7.3B2.4.3 — Unified Semantic Counterpart + Evidence Quality Audit.

READ ONLY / diagnostic only.

B2.4.2 proved that the current recorded Unified scores are reproducible with the
production formula and that the remaining divergence is NOT an input-shape
score-dilution problem. This phase therefore does two narrower jobs:

1. rank possible semantic counterparts across Legacy and Current Domain without
   creating aliases or changing identity;
2. expose deterministic evidence-quality review signals for the CURRENT Unified
   matches, especially cover/brief-recap/restatement risks.

Candidate ranking is discovery only. It is never Truth, never an identity merge,
and never a runtime matching rule.
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
from project_requirement_unified_reconciliation import (
    reconcile_unified_requirement_sets,
)

SEMANTIC_AUDIT_VERSION = "V28.7.3B2.4.3"

_PLATFORM_TITLES = {"instagram", "tiktok", "youtube", "kwai", "reels", "stories"}


@dataclass(frozen=True)
class UnifiedSemanticAudit:
    project_id: str
    status: str
    legacy_divergent_match_count: int
    domain_only_match_count: int
    high_review_risk_match_count: int
    restatement_review_match_count: int
    counterpart_candidate_row_count: int
    exact_score_parity: bool
    detail_rows: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SEMANTIC_AUDIT_VERSION,
            "project_id": self.project_id,
            "status": self.status,
            "legacy_divergent_match_count": self.legacy_divergent_match_count,
            "domain_only_match_count": self.domain_only_match_count,
            "high_review_risk_match_count": self.high_review_risk_match_count,
            "restatement_review_match_count": self.restatement_review_match_count,
            "counterpart_candidate_row_count": self.counterpart_candidate_row_count,
            "exact_score_parity": self.exact_score_parity,
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


def _normalised_platform_title(value: Any) -> str | None:
    from project_intelligence_unified import _norm
    norm = _norm(value).strip(" ;.:")
    return norm if norm in _PLATFORM_TITLES else None


def _evidence_quality_signals(
    requirement: Mapping[str, Any],
    match: Mapping[str, Any],
) -> tuple[str, tuple[str, ...]]:
    from project_intelligence_unified import _norm

    evidence = match.get("evidence") if isinstance(match.get("evidence"), Mapping) else {}
    evidence_text = str(evidence.get("text") or "").strip()
    evidence_norm = _norm(evidence_text)
    locator = str(evidence.get("locator_text") or "").casefold()
    title = str(requirement.get("title") or "")
    platform = _normalised_platform_title(title)

    flags: list[str] = []

    page_one = locator in {"page 1", "slide 1"}
    title_like = (
        len(evidence_text) <= 140
        or evidence_norm.startswith("national launch")
        or evidence_norm.startswith("lancamento")
    )
    if page_one and title_like:
        flags.append("COVER_OR_TITLE_PAGE_RISK")

    if any(marker in evidence_norm for marker in (
        "brief recap", "our goal", "briefing recap", "brief summary",
    )):
        flags.append("BRIEF_RECAP_RESTATEMENT_RISK")

    if platform == "stories":
        if "instagram" not in evidence_norm and "reels" not in evidence_norm:
            flags.append("AMBIGUOUS_STORIES_TERM_RISK")

    if platform in {"instagram", "tiktok", "youtube", "kwai"}:
        if "brief recap" in evidence_norm or "our goal" in evidence_norm:
            flags.append("PLATFORM_MENTION_IN_RECAP_RISK")

    if platform in {"reels", "stories"}:
        if platform not in evidence_norm:
            flags.append("FORMAT_NAME_NOT_EXPLICIT_IN_EVIDENCE")

    if "COVER_OR_TITLE_PAGE_RISK" in flags or "AMBIGUOUS_STORIES_TERM_RISK" in flags:
        return "HIGH_REVIEW_RISK", tuple(flags)
    if any(flag.endswith("RESTATEMENT_RISK") or flag.endswith("RECAP_RISK") for flag in flags):
        return "REVIEW_RESTATEMENT_RISK", tuple(flags)
    return "NO_AUTOMATIC_QUALITY_FLAG", tuple(flags)


def _candidate_score(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> tuple[float, dict[str, Any]]:
    """Diagnostic-only counterpart score; never used as identity Truth."""
    from project_intelligence_unified import _match_score, _norm, _tokens

    left_title = str(left.get("title") or "")
    right_title = str(right.get("title") or "")
    left_full = _matcher_input(left)
    right_full = _matcher_input(right)

    title_score = _match_score(left_title, right_title)
    full_score = _match_score(left_full, right_full)

    lt = _tokens(left_title)
    rt = _tokens(right_title)
    title_overlap = len(lt & rt) / max(1, min(len(lt), len(rt))) if lt and rt else 0.0

    left_type = str(left.get("requirement_type") or "").casefold()
    right_type = str(right.get("requirement_type") or "").casefold()
    type_match = bool(left_type and right_type and left_type == right_type)

    # Rank-only blend. The raw sub-scores are exported so humans can inspect it.
    rank_score = max(title_score, full_score, title_overlap * 0.92)
    if type_match:
        rank_score = min(0.99, rank_score + 0.04)

    exact_title = bool(_norm(left_title) and _norm(left_title) == _norm(right_title))
    return rank_score, {
        "candidate_title_score": round(title_score, 4),
        "candidate_full_score": round(full_score, 4),
        "candidate_title_overlap": round(title_overlap, 4),
        "candidate_type_match": type_match,
        "candidate_exact_normalized_title": exact_title,
        "candidate_shared_title_tokens": " | ".join(sorted(lt & rt)),
    }


def _top_candidates(
    source: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    *,
    limit: int = 5,
) -> list[tuple[float, dict[str, Any], dict[str, Any]]]:
    scored: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
    for raw in candidates:
        candidate = dict(raw)
        score, meta = _candidate_score(source, candidate)
        if score <= 0:
            continue
        scored.append((score, candidate, meta))
    scored.sort(
        key=lambda item: (
            -item[0],
            str(item[1].get("title") or "").casefold(),
            str(item[1].get("id") or ""),
        )
    )
    return scored[:limit]


def audit_unified_semantic_counterparts(
    *,
    project_id: str,
    legacy_requirement_rows: Sequence[Mapping[str, Any]],
    domain_requirement_rows: Sequence[Mapping[str, Any]],
    legacy_unified: Mapping[str, Any],
    domain_unified: Mapping[str, Any],
    compatibility: Any,
) -> UnifiedSemanticAudit:
    legacy_idx = _req_index(legacy_requirement_rows)
    domain_idx = _req_index(domain_requirement_rows)
    legacy_matches = _match_index(legacy_unified)
    domain_matches = _match_index(domain_unified)
    legacy_to_domain, domain_to_legacy = compatibility_alias_maps(compatibility)

    legacy_divergent = [
        legacy_id for legacy_id in legacy_matches
        if legacy_id not in legacy_to_domain
    ]
    domain_only = [
        domain_id for domain_id in domain_matches
        if not domain_to_legacy.get(domain_id)
    ]

    detail: list[dict[str, Any]] = []
    high_risk = 0
    restatement_risk = 0

    def emit(
        *,
        side: str,
        source_id: str,
        source_req: Mapping[str, Any],
        source_match: Mapping[str, Any],
        opposite_rows: Sequence[Mapping[str, Any]],
    ) -> None:
        nonlocal high_risk, restatement_risk
        quality_status, flags = _evidence_quality_signals(source_req, source_match)
        if quality_status == "HIGH_REVIEW_RISK":
            high_risk += 1
        elif quality_status == "REVIEW_RESTATEMENT_RISK":
            restatement_risk += 1

        evidence = source_match.get("evidence") if isinstance(source_match.get("evidence"), Mapping) else {}
        candidates = _top_candidates(source_req, opposite_rows, limit=5)

        base = {
            "divergence_side": side,
            "source_requirement_id": source_id,
            "source_title": source_req.get("title"),
            "source_type": source_req.get("requirement_type"),
            "source_match_score": source_match.get("score"),
            "evidence_quality_status": quality_status,
            "evidence_quality_flags": " | ".join(flags),
            "evidence_id": evidence.get("evidence_id"),
            "evidence_source": evidence.get("source_name"),
            "evidence_locator": evidence.get("locator_text"),
            "evidence_text": evidence.get("text"),
        }

        if not candidates:
            detail.append({
                **base,
                "candidate_rank": None,
                "candidate_requirement_id": None,
                "candidate_title": None,
                "candidate_type": None,
                "candidate_truth_state": None,
                "candidate_legacy_source_id": None,
                "candidate_already_structurally_bound": None,
                "candidate_rank_score": None,
            })
            return

        for rank, (score, candidate, meta) in enumerate(candidates, start=1):
            candidate_id = str(candidate.get("id") or "")
            if side == "legacy":
                bound = bool(domain_to_legacy.get(candidate_id))
                legacy_source_id = candidate.get("legacy_source_id")
            else:
                bound = candidate_id in legacy_to_domain
                legacy_source_id = candidate.get("id")
            detail.append({
                **base,
                "candidate_rank": rank,
                "candidate_requirement_id": candidate_id,
                "candidate_title": candidate.get("title"),
                "candidate_type": candidate.get("requirement_type"),
                "candidate_truth_state": candidate.get("truth_state"),
                "candidate_legacy_source_id": legacy_source_id,
                "candidate_already_structurally_bound": bound,
                "candidate_rank_score": round(score, 4),
                **meta,
            })

    domain_rows = [dict(row) for row in domain_idx.values()]
    legacy_rows = [dict(row) for row in legacy_idx.values()]

    for legacy_id in sorted(legacy_divergent):
        emit(
            side="legacy",
            source_id=legacy_id,
            source_req=legacy_idx.get(legacy_id, {}),
            source_match=legacy_matches[legacy_id],
            opposite_rows=domain_rows,
        )

    for domain_id in sorted(domain_only):
        emit(
            side="domain",
            source_id=domain_id,
            source_req=domain_idx.get(domain_id, {}),
            source_match=domain_matches[domain_id],
            opposite_rows=legacy_rows,
        )

    # B2.4.2 already established score parity; keep a consistency signal here.
    exact_score_parity = True
    from project_requirement_unified_input_audit import _production_briefing_pair_score
    for req_id, match in legacy_matches.items():
        req = legacy_idx.get(req_id)
        evidence = match.get("evidence") if isinstance(match.get("evidence"), Mapping) else {}
        if not req or not evidence:
            continue
        recomputed = round(_production_briefing_pair_score(_matcher_input(req), str(evidence.get("text") or "")), 4)
        recorded = round(float(match.get("score") or 0.0), 4)
        if recomputed != recorded:
            exact_score_parity = False
            break

    if not exact_score_parity:
        status = "BLOCKED_SCORE_PARITY_DRIFT"
    elif high_risk or restatement_risk:
        status = "SEMANTIC_AND_EVIDENCE_REVIEW_REQUIRED"
    elif legacy_divergent or domain_only:
        status = "SEMANTIC_COUNTERPART_REVIEW_REQUIRED"
    else:
        status = "PASS"

    detail.sort(
        key=lambda row: (
            str(row.get("divergence_side") or ""),
            str(row.get("source_title") or "").casefold(),
            int(row.get("candidate_rank") or 999),
        )
    )

    return UnifiedSemanticAudit(
        project_id=str(project_id),
        status=status,
        legacy_divergent_match_count=len(legacy_divergent),
        domain_only_match_count=len(domain_only),
        high_review_risk_match_count=high_risk,
        restatement_review_match_count=restatement_risk,
        counterpart_candidate_row_count=len(detail),
        exact_score_parity=exact_score_parity,
        detail_rows=tuple(detail),
    )


def _rows(response: Any) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in (getattr(response, "data", None) or [])
        if isinstance(row, Mapping)
    ]


def run_unified_semantic_audit(client: Any, *, project_id: str) -> UnifiedSemanticAudit:
    from project_intelligence_unified import build_unified_project_snapshot
    from project_workspace_db import fetch_project_workspace_snapshot

    compatibility = load_requirement_compatibility(client, project_id=project_id)
    if not compatibility.pass_data_bridge:
        raise RuntimeError("B2.4.3 BLOCKED: compatibility bridge is not PASS_DATA_BRIDGE.")

    source_snapshot = fetch_project_workspace_snapshot(client, project_id=project_id)
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

    reconciliation = reconcile_unified_requirement_sets(
        project_id=project_id,
        legacy_requirement_rows=[
            dict(row) for row in (source_snapshot.get("briefing_requirements") or [])
            if isinstance(row, Mapping)
        ],
        domain_requirement_rows=[
            dict(row) for row in (domain_shadow.get("briefing_requirements") or [])
            if isinstance(row, Mapping)
        ],
        legacy_link_rows=[
            dict(row) for row in (source_snapshot.get("briefing_links") or [])
            if isinstance(row, Mapping)
        ],
        legacy_unified=legacy_unified,
        domain_unified=domain_unified,
        compatibility=compatibility,
    )
    if reconciliation.mapped_legacy_missing_in_domain_count:
        raise RuntimeError(
            "B2.4.3 BLOCKED: mapped Legacy Unified match is missing in Domain."
        )

    return audit_unified_semantic_counterparts(
        project_id=project_id,
        legacy_requirement_rows=[
            dict(row) for row in (source_snapshot.get("briefing_requirements") or [])
            if isinstance(row, Mapping)
        ],
        domain_requirement_rows=[
            dict(row) for row in (domain_shadow.get("briefing_requirements") or [])
            if isinstance(row, Mapping)
        ],
        legacy_unified=legacy_unified,
        domain_unified=domain_unified,
        compatibility=compatibility,
    )
