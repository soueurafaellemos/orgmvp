from __future__ import annotations

"""NAVE V28.7.3B2.4.1 — Unified Matcher Input-Shape Audit.

READ ONLY / diagnostic only.

This audit does NOT create aliases. It asks a narrower question:
when a Legacy Unified match has no structural Domain alias, does Current Domain
already contain an EXACT normalized-title counterpart whose richer matcher input
changes the score against the SAME proposal evidence?

That distinguishes:
- missing identity lineage / input-shape dilution;
- genuinely absent Domain requirements;
- current Unified false-positive candidates.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from project_requirement_compatibility import (
    load_requirement_compatibility,
)
from project_requirement_relational_shadow import (
    build_domain_relational_shadow_snapshot,
)
from project_requirement_unified_reconciliation import (
    reconcile_unified_requirement_sets,
)


INPUT_SHAPE_AUDIT_VERSION = "V28.7.3B2.4.1"
MATCH_THRESHOLD = 0.38


@dataclass(frozen=True)
class UnifiedInputShapeAudit:
    project_id: str
    status: str
    legacy_divergent_match_count: int
    legacy_divergent_with_exact_domain_title: int
    legacy_divergent_without_exact_domain_title: int
    exact_title_score_dilution_count: int
    domain_only_match_count: int
    detail_rows: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": INPUT_SHAPE_AUDIT_VERSION,
            "project_id": self.project_id,
            "status": self.status,
            "legacy_divergent_match_count": self.legacy_divergent_match_count,
            "legacy_divergent_with_exact_domain_title":
                self.legacy_divergent_with_exact_domain_title,
            "legacy_divergent_without_exact_domain_title":
                self.legacy_divergent_without_exact_domain_title,
            "exact_title_score_dilution_count":
                self.exact_title_score_dilution_count,
            "domain_only_match_count": self.domain_only_match_count,
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


def _matcher_input(requirement: Mapping[str, Any]) -> str:
    return " ".join(
        str(requirement.get(key) or "")
        for key in ("title", "description", "source_quote", "requirement_type")
    ).strip()


def _evidence(match: Mapping[str, Any]) -> Mapping[str, Any]:
    value = match.get("evidence")
    return value if isinstance(value, Mapping) else {}


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


def _requirement_index(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for raw in rows:
        row = dict(raw)
        req_id = _text(row, "id", "requirement_id", "resolved_domain_id")
        if req_id:
            result[req_id] = row
    return result


def audit_unified_input_shape(
    *,
    project_id: str,
    legacy_requirement_rows: Sequence[Mapping[str, Any]],
    domain_requirement_rows: Sequence[Mapping[str, Any]],
    legacy_unified: Mapping[str, Any],
    domain_unified: Mapping[str, Any],
    compatibility: Any,
) -> UnifiedInputShapeAudit:
    # Import the exact production matcher helpers. This audit must observe the
    # current algorithm rather than reimplementing it differently.
    from project_intelligence_unified import _match_score, _norm, _tokens

    legacy_idx = _requirement_index(legacy_requirement_rows)
    domain_idx = _requirement_index(domain_requirement_rows)
    legacy_matches = _match_index(legacy_unified)
    domain_matches = _match_index(domain_unified)

    legacy_to_domain: dict[str, str] = {}
    domain_to_legacy: dict[str, tuple[str, ...]] = {}
    from project_requirement_compatibility import compatibility_alias_maps
    legacy_to_domain, domain_to_legacy = compatibility_alias_maps(compatibility)

    domain_by_exact_title: dict[str, list[dict[str, Any]]] = {}
    for row in domain_idx.values():
        title_norm = _norm(row.get("title"))
        if title_norm:
            domain_by_exact_title.setdefault(title_norm, []).append(row)

    detail: list[dict[str, Any]] = []
    divergent_legacy = [
        legacy_id
        for legacy_id in legacy_matches
        if legacy_id not in legacy_to_domain
    ]

    exact_counter = 0
    dilution_counter = 0

    for legacy_id in divergent_legacy:
        legacy_req = legacy_idx.get(legacy_id, {})
        legacy_match = legacy_matches[legacy_id]
        ev = _evidence(legacy_match)
        evidence_text = str(ev.get("text") or "")
        legacy_input = _matcher_input(legacy_req)
        exact_candidates = domain_by_exact_title.get(
            _norm(legacy_req.get("title")),
            [],
        )

        if exact_candidates:
            exact_counter += 1

        if not exact_candidates:
            detail.append({
                "finding_type": "legacy_match_no_exact_domain_title",
                "legacy_requirement_id": legacy_id,
                "legacy_title": legacy_req.get("title"),
                "legacy_type": legacy_req.get("requirement_type"),
                "legacy_score_recorded": legacy_match.get("score"),
                "legacy_score_same_evidence":
                    round(_match_score(legacy_input, evidence_text), 4),
                "legacy_input_chars": len(legacy_input),
                "legacy_input_tokens": len(_tokens(legacy_input)),
                "domain_requirement_id": None,
                "domain_title": None,
                "domain_score_same_evidence": None,
                "domain_input_chars": None,
                "domain_input_tokens": None,
                "same_evidence_threshold_result": "NO_EXACT_DOMAIN_TITLE",
                "evidence_id": ev.get("evidence_id"),
                "evidence_source": ev.get("source_name"),
                "evidence_locator": ev.get("locator_text"),
                "evidence_text": evidence_text,
            })
            continue

        for domain_req in exact_candidates:
            domain_id = str(domain_req.get("id") or "")
            domain_input = _matcher_input(domain_req)
            domain_same_score = _match_score(domain_input, evidence_text)
            legacy_same_score = _match_score(legacy_input, evidence_text)

            if legacy_same_score >= MATCH_THRESHOLD and domain_same_score < MATCH_THRESHOLD:
                outcome = "EXACT_DOMAIN_TITLE_SCORE_DILUTION"
                dilution_counter += 1
            elif domain_same_score >= MATCH_THRESHOLD:
                outcome = "EXACT_DOMAIN_TITLE_WOULD_MATCH_SAME_EVIDENCE"
            else:
                outcome = "EXACT_DOMAIN_TITLE_BOTH_BELOW_THRESHOLD"

            detail.append({
                "finding_type": "legacy_match_exact_domain_title_candidate",
                "legacy_requirement_id": legacy_id,
                "legacy_title": legacy_req.get("title"),
                "legacy_type": legacy_req.get("requirement_type"),
                "legacy_score_recorded": legacy_match.get("score"),
                "legacy_score_same_evidence": round(legacy_same_score, 4),
                "legacy_input_chars": len(legacy_input),
                "legacy_input_tokens": len(_tokens(legacy_input)),
                "domain_requirement_id": domain_id,
                "domain_title": domain_req.get("title"),
                "domain_type": domain_req.get("requirement_type"),
                "domain_truth_state": domain_req.get("truth_state"),
                "domain_score_recorded":
                    (domain_matches.get(domain_id) or {}).get("score"),
                "domain_score_same_evidence": round(domain_same_score, 4),
                "domain_input_chars": len(domain_input),
                "domain_input_tokens": len(_tokens(domain_input)),
                "same_evidence_threshold_result": outcome,
                "input_char_ratio_domain_vs_legacy": (
                    round(len(domain_input) / max(1, len(legacy_input)), 3)
                ),
                "input_token_ratio_domain_vs_legacy": (
                    round(
                        len(_tokens(domain_input))
                        / max(1, len(_tokens(legacy_input))),
                        3,
                    )
                ),
                "evidence_id": ev.get("evidence_id"),
                "evidence_source": ev.get("source_name"),
                "evidence_locator": ev.get("locator_text"),
                "evidence_text": evidence_text,
                "legacy_matcher_input": legacy_input,
                "domain_matcher_input": domain_input,
            })

    # Domain matches with no Legacy structural alias are also inspected for the
    # current match mechanics. This does not judge semantic truth automatically.
    domain_only = [
        domain_id
        for domain_id in domain_matches
        if not domain_to_legacy.get(domain_id)
    ]
    for domain_id in domain_only:
        domain_req = domain_idx.get(domain_id, {})
        domain_match = domain_matches[domain_id]
        ev = _evidence(domain_match)
        evidence_text = str(ev.get("text") or "")
        domain_input = _matcher_input(domain_req)
        shared_tokens = sorted(_tokens(domain_input) & _tokens(evidence_text))
        detail.append({
            "finding_type": "domain_match_without_structural_legacy_alias",
            "legacy_requirement_id": None,
            "legacy_title": None,
            "legacy_score_recorded": None,
            "legacy_score_same_evidence": None,
            "legacy_input_chars": None,
            "legacy_input_tokens": None,
            "domain_requirement_id": domain_id,
            "domain_title": domain_req.get("title"),
            "domain_type": domain_req.get("requirement_type"),
            "domain_truth_state": domain_req.get("truth_state"),
            "domain_score_recorded": domain_match.get("score"),
            "domain_score_same_evidence":
                round(_match_score(domain_input, evidence_text), 4),
            "domain_input_chars": len(domain_input),
            "domain_input_tokens": len(_tokens(domain_input)),
            "same_evidence_threshold_result": "DOMAIN_ONLY_CURRENT_MATCH",
            "shared_token_count": len(shared_tokens),
            "shared_tokens": " | ".join(shared_tokens),
            "evidence_id": ev.get("evidence_id"),
            "evidence_source": ev.get("source_name"),
            "evidence_locator": ev.get("locator_text"),
            "evidence_text": evidence_text,
            "domain_matcher_input": domain_input,
        })

    # If exact-title counterparts exist but their richer input suppresses the
    # same evidence below threshold, calibration is now evidenced.
    if dilution_counter:
        status = "INPUT_SHAPE_CALIBRATION_REQUIRED"
    elif exact_counter:
        status = "IDENTITY_LINEAGE_REVIEW_REQUIRED"
    elif divergent_legacy or domain_only:
        status = "SEMANTIC_SET_REVIEW_REQUIRED"
    else:
        status = "PASS"

    detail.sort(
        key=lambda row: (
            str(row.get("finding_type") or ""),
            str(row.get("legacy_title") or row.get("domain_title") or "").casefold(),
            str(row.get("legacy_requirement_id") or row.get("domain_requirement_id") or ""),
        )
    )

    return UnifiedInputShapeAudit(
        project_id=str(project_id),
        status=status,
        legacy_divergent_match_count=len(divergent_legacy),
        legacy_divergent_with_exact_domain_title=exact_counter,
        legacy_divergent_without_exact_domain_title=
            len(divergent_legacy) - exact_counter,
        exact_title_score_dilution_count=dilution_counter,
        domain_only_match_count=len(domain_only),
        detail_rows=tuple(detail),
    )


def _rows(response: Any) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in (getattr(response, "data", None) or [])
        if isinstance(row, Mapping)
    ]


def run_unified_input_shape_audit(
    client: Any,
    *,
    project_id: str,
) -> UnifiedInputShapeAudit:
    from project_intelligence_unified import build_unified_project_snapshot
    from project_workspace_db import fetch_project_workspace_snapshot

    compatibility = load_requirement_compatibility(
        client,
        project_id=project_id,
    )
    if not compatibility.pass_data_bridge:
        raise RuntimeError(
            "B2.4.1 BLOCKED: B2.1 compatibility is not PASS_DATA_BRIDGE."
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

    # Keep the B2.4 result as a guard: if a mapped Legacy match was truly lost,
    # B2.4.1 must not reinterpret it as a harmless shape issue.
    reconciliation = reconcile_unified_requirement_sets(
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
    if reconciliation.mapped_legacy_missing_in_domain_count:
        raise RuntimeError(
            "B2.4.1 BLOCKED: mapped Legacy Unified match is missing in Domain."
        )

    return audit_unified_input_shape(
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
