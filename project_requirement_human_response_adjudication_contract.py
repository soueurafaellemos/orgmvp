from __future__ import annotations

"""NAVE V28.7.3B2.12 — Human Response Adjudication Contract.

READ ONLY with exportable human decision package.

B2.12 turns B2.11 review rows into an explicit human adjudication queue.
It does not write to Supabase, does not change requirement Truth, and does not
change any served consumer.

Nothing is confirmed by default. A human must explicitly choose a decision.
The exported package preserves the candidate snapshot and its provenance.
"""

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Mapping, Sequence
from datetime import datetime, timezone

from project_requirement_response_recall_review_projection import (
    RESPONSE_RECALL_REVIEW_PROJECTION_VERSION,
    run_response_recall_review_projection,
)
from project_requirement_obligation_atom_gate import OBLIGATION_ATOM_VERSION
from project_requirement_response_contract_canary import RESPONSE_CONTRACT_VERSION

HUMAN_RESPONSE_ADJUDICATION_VERSION = "V28.7.3B2.12"

DECISION_CONFIRM_RESPONSE = "confirm_response"
DECISION_PARTIAL_RESPONSE = "partial_response"
DECISION_REJECT_MATCH = "reject_match"
DECISION_VISUAL_STRUCTURED_REVIEW = "visual_structured_review"
DECISION_DEFER = "defer"

VALID_DECISIONS = (
    DECISION_CONFIRM_RESPONSE,
    DECISION_PARTIAL_RESPONSE,
    DECISION_REJECT_MATCH,
    DECISION_VISUAL_STRUCTURED_REVIEW,
    DECISION_DEFER,
)

DECISION_LABELS_PT = {
    "": "— Selecione —",
    DECISION_CONFIRM_RESPONSE: "Confirmar resposta",
    DECISION_PARTIAL_RESPONSE: "Resposta parcial",
    DECISION_REJECT_MATCH: "Rejeitar correspondência",
    DECISION_VISUAL_STRUCTURED_REVIEW: "Requer revisão visual/estruturada",
    DECISION_DEFER: "Adiar decisão",
}
LABEL_TO_DECISION = {label: code for code, label in DECISION_LABELS_PT.items() if code}

ADJUDICATABLE_PROJECTION_STATUSES = {
    "response_review_high_confidence",
    "response_review_visual_or_structured_evidence",
    "response_review_partial",
    "response_review_existing_evidence",
}

DECISIVE_DECISIONS = {
    DECISION_CONFIRM_RESPONSE,
    DECISION_PARTIAL_RESPONSE,
    DECISION_REJECT_MATCH,
}


@dataclass(frozen=True)
class HumanAdjudicationQueue:
    project_id: str
    source_projection_status: str
    total_requirements: int
    queue_count: int
    high_confidence_count: int
    partial_count: int
    visual_or_structured_count: int
    existing_review_count: int
    context_false_positive_excluded_count: int
    context_no_safe_response_count: int
    queue_rows: tuple[dict[str, Any], ...]
    context_rows: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": HUMAN_RESPONSE_ADJUDICATION_VERSION,
            "project_id": self.project_id,
            "source_projection_version": RESPONSE_RECALL_REVIEW_PROJECTION_VERSION,
            "source_projection_status": self.source_projection_status,
            "total_requirements": self.total_requirements,
            "queue_count": self.queue_count,
            "high_confidence_count": self.high_confidence_count,
            "partial_count": self.partial_count,
            "visual_or_structured_count": self.visual_or_structured_count,
            "existing_review_count": self.existing_review_count,
            "context_false_positive_excluded_count": self.context_false_positive_excluded_count,
            "context_no_safe_response_count": self.context_no_safe_response_count,
            "persistence_performed": False,
            "truth_changed": False,
            "cutover_approved": False,
            "queue_rows": list(self.queue_rows),
            "context_rows": list(self.context_rows),
        }


@dataclass(frozen=True)
class HumanAdjudicationPackage:
    project_id: str
    package_status: str
    reviewer: str
    adjudicated_at_utc: str
    queue_count: int
    explicitly_decided_count: int
    undecided_count: int
    confirmed_count: int
    partial_count: int
    rejected_count: int
    visual_review_count: int
    deferred_count: int
    validation_errors: tuple[str, ...]
    decision_rows: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": HUMAN_RESPONSE_ADJUDICATION_VERSION,
            "project_id": self.project_id,
            "package_status": self.package_status,
            "reviewer": self.reviewer,
            "adjudicated_at_utc": self.adjudicated_at_utc,
            "queue_count": self.queue_count,
            "explicitly_decided_count": self.explicitly_decided_count,
            "undecided_count": self.undecided_count,
            "confirmed_count": self.confirmed_count,
            "partial_count": self.partial_count,
            "rejected_count": self.rejected_count,
            "visual_review_count": self.visual_review_count,
            "deferred_count": self.deferred_count,
            "validation_errors": list(self.validation_errors),
            "persistence_performed": False,
            "truth_changed": False,
            "cutover_approved": False,
            "decision_rows": list(self.decision_rows),
        }


def _stable_candidate_id(project_id: str, row: Mapping[str, Any]) -> str:
    current_evidence = row.get("current_response_evidence") or []
    current_ids = ",".join(sorted(
        str(item.get("evidence_id") or "")
        for item in current_evidence
        if isinstance(item, Mapping)
    ))
    payload = "|".join([
        str(project_id),
        str(row.get("requirement_id") or ""),
        str(row.get("recall_evidence_id") or ""),
        current_ids,
        str(row.get("projected_response_status") or ""),
        RESPONSE_RECALL_REVIEW_PROJECTION_VERSION,
        OBLIGATION_ATOM_VERSION,
        RESPONSE_CONTRACT_VERSION,
    ])
    return sha256(payload.encode("utf-8")).hexdigest()[:24]


def _candidate_snapshot(project_id: str, raw: Mapping[str, Any]) -> dict[str, Any]:
    row = dict(raw)
    return {
        "candidate_id": _stable_candidate_id(project_id, row),
        "project_id": str(project_id),
        "requirement_id": row.get("requirement_id"),
        "requirement_title": row.get("title"),
        "requirement_type": row.get("requirement_type"),
        "mandatory": row.get("mandatory"),
        "priority": row.get("priority"),
        "truth_status_at_review": row.get("truth_status"),
        "current_response_contract_status": row.get("current_response_contract_status"),
        "projected_response_status": row.get("projected_response_status"),
        "projected_reason": row.get("projected_reason"),
        "review_origin": row.get("review_origin"),
        "current_response_evidence_count": row.get("current_response_evidence_count"),
        "current_response_evidence": row.get("current_response_evidence"),
        "evidence_id": row.get("recall_evidence_id"),
        "evidence_source": row.get("recall_evidence_source"),
        "evidence_locator": row.get("recall_evidence_locator"),
        "evidence_text": row.get("recall_candidate_text"),
        "recall_gate_class": row.get("recall_gate_class"),
        "obligation_atom_coverage": row.get("recall_obligation_atom_coverage"),
        "title_anchor_coverage": row.get("recall_title_anchor_coverage"),
        "requirement_atoms": row.get("recall_requirement_atoms"),
        "shared_atoms": row.get("recall_shared_atoms"),
        "missing_atoms": row.get("recall_missing_atoms"),
        "missing_hard_atoms": row.get("recall_missing_hard_atoms"),
        "source_projection_version": RESPONSE_RECALL_REVIEW_PROJECTION_VERSION,
        "source_atom_gate_version": OBLIGATION_ATOM_VERSION,
        "source_response_contract_version": RESPONSE_CONTRACT_VERSION,
    }


def build_human_adjudication_queue(
    *,
    project_id: str,
    projection: Any,
) -> HumanAdjudicationQueue:
    if str(getattr(projection, "project_id", project_id)) != str(project_id):
        raise ValueError("B2.12 project mismatch with B2.11 projection")

    queue_rows: list[dict[str, Any]] = []
    context_rows: list[dict[str, Any]] = []

    for raw in getattr(projection, "requirement_rows", ()) or ():
        row = dict(raw)
        status = str(row.get("projected_response_status") or "")
        if status in ADJUDICATABLE_PROJECTION_STATUSES:
            queue_rows.append(_candidate_snapshot(project_id, row))
        elif status in {"false_positive_excluded", "no_safely_verified_response"}:
            context_rows.append({
                "requirement_id": row.get("requirement_id"),
                "requirement_title": row.get("title"),
                "projected_response_status": status,
                "projected_reason": row.get("projected_reason"),
                "recall_gate_class": row.get("recall_gate_class"),
                "evidence_locator": row.get("recall_evidence_locator"),
                "evidence_text": row.get("recall_candidate_text"),
            })

    queue_rows.sort(
        key=lambda row: (
            0 if row["projected_response_status"] == "response_review_high_confidence" else
            1 if row["projected_response_status"] == "response_review_visual_or_structured_evidence" else
            2 if row["projected_response_status"] == "response_review_partial" else 3,
            str(row.get("requirement_title") or "").casefold(),
        )
    )

    return HumanAdjudicationQueue(
        project_id=str(project_id),
        source_projection_status=str(getattr(projection, "status", "")),
        total_requirements=int(getattr(projection, "total_requirements", len(queue_rows) + len(context_rows))),
        queue_count=len(queue_rows),
        high_confidence_count=sum(r["projected_response_status"] == "response_review_high_confidence" for r in queue_rows),
        partial_count=sum(r["projected_response_status"] == "response_review_partial" for r in queue_rows),
        visual_or_structured_count=sum(r["projected_response_status"] == "response_review_visual_or_structured_evidence" for r in queue_rows),
        existing_review_count=sum(r["projected_response_status"] == "response_review_existing_evidence" for r in queue_rows),
        context_false_positive_excluded_count=sum(r["projected_response_status"] == "false_positive_excluded" for r in context_rows),
        context_no_safe_response_count=sum(r["projected_response_status"] == "no_safely_verified_response" for r in context_rows),
        queue_rows=tuple(queue_rows),
        context_rows=tuple(context_rows),
    )


def _normalize_timestamp(value: str | None) -> str:
    if value:
        return str(value)
    return datetime.now(timezone.utc).isoformat()


def build_human_adjudication_package(
    *,
    queue: HumanAdjudicationQueue,
    reviewer: str,
    edited_rows: Sequence[Mapping[str, Any]],
    adjudicated_at_utc: str | None = None,
) -> HumanAdjudicationPackage:
    source_by_id = {str(r["candidate_id"]): dict(r) for r in queue.queue_rows}
    edits_by_id: dict[str, dict[str, Any]] = {}
    for raw in edited_rows:
        row = dict(raw)
        cid = str(row.get("candidate_id") or "")
        if cid and cid in source_by_id:
            edits_by_id[cid] = row

    reviewer = str(reviewer or "").strip()
    errors: list[str] = []
    decision_rows: list[dict[str, Any]] = []
    explicit_count = 0

    for cid, source in source_by_id.items():
        edit = edits_by_id.get(cid, {})
        decision = str(edit.get("decision") or "").strip()
        note = str(edit.get("human_rationale") or "").strip()

        if not decision:
            decision_rows.append({
                **source,
                "decision_explicit": False,
                "human_decision": "",
                "human_decision_label": "",
                "human_rationale": note,
                "reviewer": "",
                "adjudicated_at_utc": "",
                "truth_effect_applied": False,
                "persistence_performed": False,
            })
            continue

        explicit_count += 1
        if decision not in VALID_DECISIONS:
            errors.append(f"{cid}: invalid decision `{decision}`")
            decision_rows.append({
                **source,
                "decision_explicit": True,
                "human_decision": decision,
                "human_decision_label": "",
                "human_rationale": note,
                "reviewer": reviewer,
                "adjudicated_at_utc": _normalize_timestamp(adjudicated_at_utc),
                "truth_effect_applied": False,
                "persistence_performed": False,
            })
            continue
        if not reviewer:
            errors.append(f"{cid}: reviewer is required for an explicit human decision")
        if decision in DECISIVE_DECISIONS and len(note) < 5:
            errors.append(f"{cid}: a human rationale of at least 5 characters is required for `{decision}`")

        decision_rows.append({
            **source,
            "decision_explicit": True,
            "human_decision": decision,
            "human_decision_label": DECISION_LABELS_PT[decision],
            "human_rationale": note,
            "reviewer": reviewer,
            "adjudicated_at_utc": _normalize_timestamp(adjudicated_at_utc),
            "truth_effect_applied": False,
            "persistence_performed": False,
        })

    explicitly_decided = explicit_count
    undecided = max(0, queue.queue_count - explicitly_decided)

    if errors:
        package_status = "INVALID_DRAFT"
    elif explicitly_decided == 0:
        package_status = "EMPTY_DRAFT"
    elif undecided:
        package_status = "PARTIAL_DRAFT"
    else:
        package_status = "COMPLETE_REVIEW_PACKAGE"

    return HumanAdjudicationPackage(
        project_id=queue.project_id,
        package_status=package_status,
        reviewer=reviewer,
        adjudicated_at_utc=_normalize_timestamp(adjudicated_at_utc),
        queue_count=queue.queue_count,
        explicitly_decided_count=explicitly_decided,
        undecided_count=undecided,
        confirmed_count=sum(r["human_decision"] == DECISION_CONFIRM_RESPONSE for r in decision_rows),
        partial_count=sum(r["human_decision"] == DECISION_PARTIAL_RESPONSE for r in decision_rows),
        rejected_count=sum(r["human_decision"] == DECISION_REJECT_MATCH for r in decision_rows),
        visual_review_count=sum(r["human_decision"] == DECISION_VISUAL_STRUCTURED_REVIEW for r in decision_rows),
        deferred_count=sum(r["human_decision"] == DECISION_DEFER for r in decision_rows),
        validation_errors=tuple(errors),
        decision_rows=tuple(decision_rows),
    )


def run_human_adjudication_queue(
    client: Any,
    *,
    project_id: str,
) -> HumanAdjudicationQueue:
    projection = run_response_recall_review_projection(
        client,
        project_id=project_id,
    )
    return build_human_adjudication_queue(
        project_id=project_id,
        projection=projection,
    )
