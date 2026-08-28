from __future__ import annotations

"""NAVE V28.7.3B2.11 — Governed Response Recall Review Projection.

READ ONLY / projection only.

B2.7.1 defines the current response contract from governed Current Domain
requirements. B2.10.1 adds recall candidates after canonical obligation
coverage calibration.

B2.11 combines those two signals into one review-oriented projection without
creating new Truth, without persisting Human Review, and without changing any
served consumer.

Critical rule:
    ONLY B2.7.1 `verified_response` remains verified.
    B2.10.1 recall — including STRICT_SAFE_AUTO_PRESERVED — remains REVIEW ONLY.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from project_requirement_response_contract_canary import (
    run_response_contract_canary,
)
from project_requirement_obligation_atom_gate import (
    run_obligation_atom_gate,
)

RESPONSE_RECALL_REVIEW_PROJECTION_VERSION = "V28.7.3B2.11"

_RECALL_PRIORITY = {
    "STRICT_SAFE_AUTO_PRESERVED": 0,
    "HIGH_CONFIDENCE_REVIEW_CANDIDATE": 1,
    "PARTIAL_OBLIGATION_COVERAGE": 2,
    "REJECT_SOURCE_ROLE_NON_RESPONSE": 3,
    "REJECT_GENERIC_OVERLAP": 4,
    "NO_CANDIDATE": 5,
}

_REVIEW_STATUSES = {
    "response_review_high_confidence",
    "response_review_visual_or_structured_evidence",
    "response_review_partial",
    "response_review_existing_evidence",
}


@dataclass(frozen=True)
class ResponseRecallReviewProjection:
    project_id: str
    status: str
    total_requirements: int
    verified_response_count: int
    high_confidence_review_count: int
    visual_or_structured_review_count: int
    partial_review_count: int
    existing_review_count: int
    false_positive_excluded_count: int
    no_safely_verified_response_count: int
    source_role_rejected_count: int
    generic_overlap_rejected_count: int
    strict_safe_recall_candidate_count: int
    requirement_rows: tuple[dict[str, Any], ...]
    semantic_response_rows: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": RESPONSE_RECALL_REVIEW_PROJECTION_VERSION,
            "project_id": self.project_id,
            "status": self.status,
            "total_requirements": self.total_requirements,
            "verified_response_count": self.verified_response_count,
            "high_confidence_review_count": self.high_confidence_review_count,
            "visual_or_structured_review_count": self.visual_or_structured_review_count,
            "partial_review_count": self.partial_review_count,
            "existing_review_count": self.existing_review_count,
            "false_positive_excluded_count": self.false_positive_excluded_count,
            "no_safely_verified_response_count": self.no_safely_verified_response_count,
            "source_role_rejected_count": self.source_role_rejected_count,
            "generic_overlap_rejected_count": self.generic_overlap_rejected_count,
            "strict_safe_recall_candidate_count": self.strict_safe_recall_candidate_count,
            "cutover_approved": False,
            "persistence_performed": False,
            "requirement_rows": list(self.requirement_rows),
            "semantic_response_rows": list(self.semantic_response_rows),
        }


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _best_recall_by_requirement(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    counts: dict[str, int] = {}

    for raw in rows:
        row = dict(raw)
        rid = str(row.get("requirement_id") or "")
        if not rid:
            continue
        grouped.setdefault(rid, []).append(row)
        counts[rid] = counts.get(rid, 0) + 1

    best: dict[str, dict[str, Any]] = {}
    for rid, candidates in grouped.items():
        ordered = sorted(
            candidates,
            key=lambda row: (
                _RECALL_PRIORITY.get(str(row.get("b210_class") or ""), 99),
                -_float(row.get("obligation_atom_coverage")),
                -_float(row.get("title_anchor_coverage")),
                str(row.get("evidence_locator") or ""),
            ),
        )
        best[rid] = ordered[0]
    return best, counts


def _project_status(
    current_status: str,
    recall_class: str,
) -> tuple[str, str, str]:
    """Return projected_status, reason, review_origin.

    This function never creates a new verified response from recall.
    """
    current_status = str(current_status or "")
    recall_class = str(recall_class or "")

    if current_status == "verified_response":
        return (
            "verified_response",
            "already verified by the governed B2.7.1 response contract",
            "current_contract",
        )

    if recall_class in {
        "STRICT_SAFE_AUTO_PRESERVED",
        "HIGH_CONFIDENCE_REVIEW_CANDIDATE",
    }:
        return (
            "response_review_high_confidence",
            "recall candidate covers the canonical obligation strongly; human review is still required",
            "recall",
        )

    if current_status == "response_review_visual_or_structured_evidence":
        return (
            "response_review_visual_or_structured_evidence",
            "current evidence is heading/structured/visual and requires human inspection",
            "current_contract",
        )

    if recall_class == "PARTIAL_OBLIGATION_COVERAGE":
        return (
            "response_review_partial",
            "recall candidate covers only part of the canonical obligation",
            "recall",
        )

    if current_status == "response_review":
        return (
            "response_review_existing_evidence",
            "current selected evidence remains insufficient for verification",
            "current_contract",
        )

    if current_status == "false_positive_excluded":
        return (
            "false_positive_excluded",
            "current selected evidence is excluded and no stronger recall candidate supersedes it",
            "current_contract",
        )

    return (
        "no_safely_verified_response",
        "no evidence candidate is safe enough to project as a verified response",
        "none",
    )


def build_response_recall_review_projection(
    *,
    project_id: str,
    response_contract: Any,
    obligation_gate: Any,
) -> ResponseRecallReviewProjection:
    contract_project = str(getattr(response_contract, "project_id", project_id))
    gate_project = str(getattr(obligation_gate, "project_id", project_id))
    if contract_project != str(project_id) or gate_project != str(project_id):
        raise ValueError("B2.11 project mismatch between response contract and obligation gate")

    best_recall, recall_counts = _best_recall_by_requirement(
        getattr(obligation_gate, "detail_rows", ()) or ()
    )

    projected_rows: list[dict[str, Any]] = []
    for raw in getattr(response_contract, "requirement_rows", ()) or ():
        req = dict(raw)
        rid = str(req.get("requirement_id") or "")
        recall = dict(best_recall.get(rid) or {})
        recall_class = str(recall.get("b210_class") or "NO_CANDIDATE")
        current_status = str(req.get("response_contract_status") or "")

        projected_status, reason, origin = _project_status(
            current_status,
            recall_class,
        )

        projected_rows.append({
            "requirement_id": rid,
            "title": req.get("title"),
            "requirement_type": req.get("requirement_type"),
            "mandatory": req.get("mandatory"),
            "priority": req.get("priority"),
            "truth_status": req.get("truth_status"),
            "current_response_contract_status": current_status,
            "projected_response_status": projected_status,
            "projected_reason": reason,
            "review_origin": origin,
            "current_response_evidence_count": req.get("response_evidence_count"),
            "current_response_evidence": req.get("response_evidence"),
            "recall_candidate_count": recall_counts.get(rid, 0),
            "recall_gate_class": recall_class,
            "recall_obligation_atom_coverage": recall.get("obligation_atom_coverage"),
            "recall_title_anchor_coverage": recall.get("title_anchor_coverage"),
            "recall_requirement_atoms": recall.get("requirement_atoms"),
            "recall_shared_atoms": recall.get("shared_atoms"),
            "recall_missing_atoms": recall.get("missing_atoms"),
            "recall_missing_hard_atoms": recall.get("missing_hard_atoms"),
            "recall_evidence_id": recall.get("evidence_id"),
            "recall_evidence_source": recall.get("evidence_source"),
            "recall_evidence_locator": recall.get("evidence_locator"),
            "recall_candidate_text": recall.get("candidate_text"),
        })

    counts = {
        "verified_response": 0,
        "response_review_high_confidence": 0,
        "response_review_visual_or_structured_evidence": 0,
        "response_review_partial": 0,
        "response_review_existing_evidence": 0,
        "false_positive_excluded": 0,
        "no_safely_verified_response": 0,
    }
    for row in projected_rows:
        status = str(row["projected_response_status"])
        if status in counts:
            counts[status] += 1

    source_role_rejected = sum(
        1
        for row in projected_rows
        if row.get("recall_gate_class") == "REJECT_SOURCE_ROLE_NON_RESPONSE"
    )
    generic_overlap_rejected = sum(
        1
        for row in projected_rows
        if row.get("recall_gate_class") == "REJECT_GENERIC_OVERLAP"
    )
    strict_safe_candidates = sum(
        1
        for row in projected_rows
        if row.get("recall_gate_class") == "STRICT_SAFE_AUTO_PRESERVED"
    )

    review_count = sum(
        1
        for row in projected_rows
        if row["projected_response_status"] in _REVIEW_STATUSES
    )
    exclusions = counts["false_positive_excluded"]

    if review_count and exclusions:
        status = "PASS_READ_ONLY_PROJECTION_WITH_REVIEW_AND_EXCLUSIONS"
    elif review_count:
        status = "PASS_READ_ONLY_PROJECTION_WITH_REVIEW"
    elif exclusions:
        status = "PASS_READ_ONLY_PROJECTION_WITH_EXCLUSIONS"
    else:
        status = "PASS_READ_ONLY_PROJECTION"

    projected_rows.sort(
        key=lambda row: (
            str(row.get("projected_response_status") or ""),
            str(row.get("title") or "").casefold(),
        )
    )

    semantic_rows = tuple(
        dict(row)
        for row in (getattr(response_contract, "semantic_response_rows", ()) or ())
    )

    return ResponseRecallReviewProjection(
        project_id=str(project_id),
        status=status,
        total_requirements=len(projected_rows),
        verified_response_count=counts["verified_response"],
        high_confidence_review_count=counts["response_review_high_confidence"],
        visual_or_structured_review_count=counts["response_review_visual_or_structured_evidence"],
        partial_review_count=counts["response_review_partial"],
        existing_review_count=counts["response_review_existing_evidence"],
        false_positive_excluded_count=counts["false_positive_excluded"],
        no_safely_verified_response_count=counts["no_safely_verified_response"],
        source_role_rejected_count=source_role_rejected,
        generic_overlap_rejected_count=generic_overlap_rejected,
        strict_safe_recall_candidate_count=strict_safe_candidates,
        requirement_rows=tuple(projected_rows),
        semantic_response_rows=semantic_rows,
    )


def run_response_recall_review_projection(
    client: Any,
    *,
    project_id: str,
) -> ResponseRecallReviewProjection:
    contract = run_response_contract_canary(
        client,
        project_id=project_id,
    )
    gate = run_obligation_atom_gate(
        client,
        project_id=project_id,
    )

    return build_response_recall_review_projection(
        project_id=project_id,
        response_contract=contract,
        obligation_gate=gate,
    )
