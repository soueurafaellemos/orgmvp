from __future__ import annotations

"""NAVE V28.7.3B2.7 — Requirement Response Contract Canary.

READ ONLY / canary projection only.

B2.6 established that:
- a governed requirement match can still be a semantic false positive;
- heading-only evidence is insufficient, but is NOT proof of a false positive
  because the page can be visually driven;
- cross-domain semantic responses must not be mislabeled as requirement compliance.

B2.7 projects the consumer-facing contract that should eventually replace the
binary "Resposta identificada" badge.

No production consumer is changed in this phase.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from project_domain_requirement_consumer import adapt_domain_requirements
from project_requirement_response_entailment_shadow import (
    run_response_entailment_shadow,
)

RESPONSE_CONTRACT_VERSION = "V28.7.3B2.7.1"

_VERIFIED = {
    "SUPPORTED_CANONICAL_ANCHORS",
    "SUPPORTED_EXPLICIT_ATOM",
}

_VISUAL_REVIEW = {
    "REVIEW_HEADING_ONLY",
}

_FALSE_POSITIVE = {
    "REVIEW_NO_TITLE_ANCHOR",
}

_SOFT_REVIEW = {
    "REVIEW_NO_CANONICAL_ANCHORS",
    "REVIEW_PARTIAL_CANONICAL_SUPPORT",
    "REVIEW_WEAK_CANONICAL_SUPPORT",
}


@dataclass(frozen=True)
class ResponseContractCanary:
    project_id: str
    status: str
    total_requirements: int
    verified_response_count: int
    response_review_count: int
    false_positive_excluded_count: int
    no_verified_response_count: int
    cross_domain_supported_count: int
    component_review_count: int
    requirement_rows: tuple[dict[str, Any], ...]
    semantic_response_rows: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": RESPONSE_CONTRACT_VERSION,
            "project_id": self.project_id,
            "status": self.status,
            "total_requirements": self.total_requirements,
            "verified_response_count": self.verified_response_count,
            "response_review_count": self.response_review_count,
            "false_positive_excluded_count": self.false_positive_excluded_count,
            "no_verified_response_count": self.no_verified_response_count,
            "cross_domain_supported_count": self.cross_domain_supported_count,
            "component_review_count": self.component_review_count,
            "requirement_rows": list(self.requirement_rows),
            "semantic_response_rows": list(self.semantic_response_rows),
        }


def _calibrated_verdict(row: Mapping[str, Any]) -> tuple[str, str]:
    status = str(row.get("entailment_status") or "")

    if status in _VERIFIED:
        return (
            "verified_response",
            "material evidence supports canonical requirement semantics",
        )

    if status in _VISUAL_REVIEW:
        return (
            "response_review_visual_or_structured_evidence",
            "parsed text is only a heading; page may require visual/structured evidence review",
        )

    if status in _FALSE_POSITIVE:
        # B2.6 only reaches this status after material/non-heading evidence survived
        # the Evidence Role Gate. Zero canonical anchor here is a high-confidence
        # mismatch, not merely sparse extraction.
        return (
            "false_positive_excluded",
            "substantive selected evidence does not support the canonical requirement",
        )

    if status in _SOFT_REVIEW:
        return (
            "response_review",
            "evidence is not strong enough for verified response",
        )

    return (
        "response_review",
        "unclassified entailment state requires review",
    )


def build_response_contract_canary(
    *,
    project_id: str,
    current_domain_requirement_rows: Sequence[Mapping[str, Any]],
    entailment_result: Any,
) -> ResponseContractCanary:
    adapted = adapt_domain_requirements(
        [dict(row) for row in current_domain_requirement_rows]
    )

    by_domain_id: dict[str, list[dict[str, Any]]] = {}
    semantic_rows: list[dict[str, Any]] = []

    for raw in entailment_result.detail_rows:
        row = dict(raw)
        disposition = str(row.get("contract_disposition") or "")
        domain_id = str(row.get("domain_requirement_id") or "")
        verdict, reason = _calibrated_verdict(row)

        if domain_id and disposition in {
            "requirement_owned_response",
            "mapped_requirement_response_asymmetry",
            "domain_requirement_response_candidate",
        }:
            by_domain_id.setdefault(domain_id, []).append({
                **row,
                "contract_verdict": verdict,
                "contract_reason": reason,
            })
            continue

        # Cross-domain answers are valuable project knowledge, but they are not
        # requirement-compliance rows.
        if disposition in {
            "cross_domain_owned_same_evidence",
            "cross_domain_candidate_review",
            "material_response_component_unowned",
            "material_response_unowned",
        }:
            semantic_status = (
                "cross_domain_response_supported"
                if verdict == "verified_response"
                and disposition == "cross_domain_owned_same_evidence"
                else "semantic_component_review"
            )
            semantic_rows.append({
                "legacy_requirement_id": row.get("legacy_requirement_id"),
                "legacy_title": row.get("legacy_title"),
                "contract_disposition": disposition,
                "semantic_response_status": semantic_status,
                "ownership_domain": row.get("ownership_domain"),
                "ownership_labels": row.get("ownership_labels"),
                "ownership_review_required":
                    bool(row.get("ownership_review_required")),
                "entailment_status": row.get("entailment_status"),
                "evidence_id": row.get("evidence_id"),
                "evidence_locator": row.get("evidence_locator"),
                "evidence_text": row.get("evidence_text"),
            })

    requirement_rows: list[dict[str, Any]] = []
    verified = 0
    review = 0
    excluded = 0
    no_response = 0

    for req in adapted:
        req_id = str(req.get("stable_key") or req.get("id") or "")
        candidates = by_domain_id.get(req_id, [])

        # If a requirement has multiple evidence candidates, prefer a verified
        # response. Otherwise expose the strongest cautionary state.
        verdicts = {str(row.get("contract_verdict") or "") for row in candidates}

        if "verified_response" in verdicts:
            response_status = "verified_response"
            verified += 1
        elif "false_positive_excluded" in verdicts:
            response_status = "false_positive_excluded"
            excluded += 1
        elif any(v.startswith("response_review") for v in verdicts):
            visual = any(
                v == "response_review_visual_or_structured_evidence"
                for v in verdicts
            )
            response_status = (
                "response_review_visual_or_structured_evidence"
                if visual
                else "response_review"
            )
            review += 1
        else:
            response_status = "no_verified_response"
            no_response += 1

        evidence_rows = []
        for row in candidates:
            evidence_rows.append({
                "verdict": row.get("contract_verdict"),
                "entailment_status": row.get("entailment_status"),
                "evidence_id": row.get("evidence_id"),
                "evidence_locator": row.get("evidence_locator"),
                "evidence_text": row.get("evidence_text"),
            })

        requirement_rows.append({
            "requirement_id": req_id,
            "title": req.get("title"),
            "requirement_type": req.get("requirement_type"),
            "mandatory": req.get("mandatory"),
            "priority": req.get("priority"),
            "truth_status": req.get("truth_status"),
            "response_contract_status": response_status,
            "response_evidence_count": len(candidates),
            "response_evidence": evidence_rows,
        })

    cross_domain_supported = sum(
        1
        for row in semantic_rows
        if row["semantic_response_status"] == "cross_domain_response_supported"
    )
    component_reviews = sum(
        1
        for row in semantic_rows
        if row["semantic_response_status"] == "semantic_component_review"
    )

    # IMPORTANT:
    # This status describes precision of the CURRENT response claims. It does not
    # declare recall completeness. `no_verified_response` can mean either the
    # proposal did not answer the requirement OR retrieval has not found the answer.
    if excluded:
        status = "BLOCKED_CURRENT_RESPONSE_FALSE_POSITIVE"
    elif review or component_reviews:
        status = "PASS_WITH_RESPONSE_REVIEW"
    else:
        status = "PASS_RESPONSE_PRECISION"

    requirement_rows.sort(
        key=lambda row: (
            str(row["response_contract_status"]),
            str(row.get("title") or "").casefold(),
        )
    )
    semantic_rows.sort(
        key=lambda row: str(row.get("legacy_title") or "").casefold()
    )

    return ResponseContractCanary(
        project_id=str(project_id),
        status=status,
        total_requirements=len(requirement_rows),
        verified_response_count=verified,
        response_review_count=review,
        false_positive_excluded_count=excluded,
        no_verified_response_count=no_response,
        cross_domain_supported_count=cross_domain_supported,
        component_review_count=component_reviews,
        requirement_rows=tuple(requirement_rows),
        semantic_response_rows=tuple(semantic_rows),
    )


CURRENT_TRUTH_STATES = {"verified", "human_confirmed"}


def _only_current_truth_requirements(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Defense-in-depth: B2.7.1 must never project Legacy/historical rows.

    The central Domain Reader already applies this policy for requirements.
    Keeping the filter here prevents a future reader/view drift from silently
    inflating the client-facing denominator.
    """
    current: list[dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        truth_state = str(
            row.get("truth_state")
            or row.get("verification_state")
            or ""
        ).casefold()
        if truth_state in CURRENT_TRUTH_STATES:
            current.append(row)
    return current


def _rows(response: Any) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in (getattr(response, "data", None) or [])
        if isinstance(row, Mapping)
    ]


def run_response_contract_canary(
    client: Any,
    *,
    project_id: str,
) -> ResponseContractCanary:
    entailment = run_response_entailment_shadow(
        client,
        project_id=project_id,
    )

    # B2.7 bugfix:
    # Do NOT query the full Truth Status view directly. That view intentionally
    # preserves verified + legacy_unverified + historical rows for audit.
    # The client-facing Current Domain denominator must come from the governed
    # Domain Reader, whose requirements candidate contains current truth only.
    from project_domain_reader import read_domain

    shadow = read_domain(
        client,
        project_id,
        "requirements",
        legacy_loader=lambda: [],
        audit=False,
    )
    if str(shadow.read_mode) != "shadow_compare":
        raise RuntimeError(
            f"B2.7.1 BLOCKED: requirements read_mode={shadow.read_mode}"
        )

    current = _only_current_truth_requirements(
        shadow.domain_candidate
    )

    return build_response_contract_canary(
        project_id=project_id,
        current_domain_requirement_rows=current,
        entailment_result=entailment,
    )
