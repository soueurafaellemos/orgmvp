from __future__ import annotations

"""NAVE V28.7.3B2.8 — Response Evidence Recall Shadow.

READ ONLY / diagnostic only.

B2.7.1 fixes the Current Domain denominator and gives us a precision-preserving
response contract. B2.8 attacks the other side of the problem: recall.

For every Current Domain requirement that is not already a verified response,
B2.8 scans proposal/final-presentation Evidence Units and asks:

    Is there a DIFFERENT material evidence unit that can support the canonical
    requirement without relaxing the precision rules established in B2.4–B2.7?

Retrieval may be permissive, but acceptance is conservative:
- proposal/final-presentation source only;
- Evidence Role Gate must retain the evidence;
- B2.6 canonical entailment must be SUPPORTED_*;
- cover/title page, Brief Recap and ambiguous lexical mentions never become
  auto-accepted recall.

No production match is changed in this phase.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from project_domain_requirement_consumer import adapt_domain_requirements
from project_requirement_response_contract_canary import (
    run_response_contract_canary,
)
from project_requirement_response_entailment_shadow import (
    response_entailment_signal,
)
from project_requirement_unified_evidence_role_shadow import (
    classify_response_evidence_role,
)

RESPONSE_RECALL_VERSION = "V28.7.3B2.8"

_ACCEPTED_ENTAILMENT = {
    "SUPPORTED_CANONICAL_ANCHORS",
    "SUPPORTED_EXPLICIT_ATOM",
}

_REVIEW_ENTAILMENT = {
    "REVIEW_HEADING_ONLY",
    "REVIEW_PARTIAL_CANONICAL_SUPPORT",
    "REVIEW_WEAK_CANONICAL_SUPPORT",
}


@dataclass(frozen=True)
class ResponseRecallShadow:
    project_id: str
    status: str
    current_requirement_count: int
    already_verified_response_count: int
    requirements_scanned_count: int
    recoverable_verified_candidate_count: int
    review_candidate_count: int
    no_candidate_count: int
    detail_rows: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": RESPONSE_RECALL_VERSION,
            "project_id": self.project_id,
            "status": self.status,
            "current_requirement_count": self.current_requirement_count,
            "already_verified_response_count":
                self.already_verified_response_count,
            "requirements_scanned_count": self.requirements_scanned_count,
            "recoverable_verified_candidate_count":
                self.recoverable_verified_candidate_count,
            "review_candidate_count": self.review_candidate_count,
            "no_candidate_count": self.no_candidate_count,
            "detail_rows": list(self.detail_rows),
        }


def _proposal_evidence(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    from project_intelligence_unified import _evidence_ref, _role_maps

    graph = snapshot.get("intelligence_graph") or {}
    roles, assets = _role_maps(graph)
    rows: list[dict[str, Any]] = []

    for raw in graph.get("evidence_units") or []:
        if not isinstance(raw, Mapping):
            continue
        row = dict(raw)
        asset_id = str(row.get("source_asset_id") or "")
        source_roles = roles.get(asset_id, set())
        if not (
            {"proposal_presentation", "final_presentation"}
            & set(source_roles)
        ):
            continue
        if not str(row.get("content_text") or "").strip():
            continue
        rows.append(_evidence_ref(row, assets, roles))

    rows.sort(
        key=lambda row: (
            str(row.get("source_name") or "").casefold(),
            int(row.get("ordinal") or 10**9),
            str(row.get("evidence_id") or ""),
        )
    )
    return rows


def _requirement_query(requirement: Mapping[str, Any]) -> str:
    return " ".join(
        str(requirement.get(key) or "")
        for key in ("title", "description", "source_excerpt", "requirement_type")
    ).strip()


def _retrieval_score(
    requirement: Mapping[str, Any],
    evidence_text: str,
) -> float:
    """Broad retrieval score only.

    This score may retrieve false positives. It is NEVER acceptance. Acceptance
    happens only after Evidence Role + B2.6 entailment.
    """
    from project_intelligence_unified import _match_score, _tokens

    query = _requirement_query(requirement)
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
    response_role: str,
    entailment_status: str,
) -> str:
    if response_role != "retain_response_candidate":
        return "EXCLUDED_NON_RESPONSE"
    if entailment_status in _ACCEPTED_ENTAILMENT:
        return "RECOVERABLE_VERIFIED_RESPONSE_CANDIDATE"
    if entailment_status in _REVIEW_ENTAILMENT:
        return "RECALL_REVIEW_CANDIDATE"
    return "NO_ACCEPTABLE_RECALL"


def audit_response_recall(
    *,
    project_id: str,
    current_requirement_rows: Sequence[Mapping[str, Any]],
    current_contract_rows: Sequence[Mapping[str, Any]],
    proposal_evidence_rows: Sequence[Mapping[str, Any]],
    top_k: int = 5,
) -> ResponseRecallShadow:
    requirements = adapt_domain_requirements(
        [dict(row) for row in current_requirement_rows]
    )
    contract_by_id = {
        str(row.get("requirement_id") or ""): dict(row)
        for row in current_contract_rows
        if row.get("requirement_id")
    }

    detail: list[dict[str, Any]] = []
    already_verified = 0
    scanned = 0
    recoverable_requirements: set[str] = set()
    review_requirements: set[str] = set()
    no_candidate_requirements: set[str] = set()

    for req in requirements:
        req_id = str(req.get("stable_key") or req.get("id") or "")
        contract = contract_by_id.get(req_id, {})
        current_status = str(
            contract.get("response_contract_status")
            or "no_verified_response"
        )

        if current_status == "verified_response":
            already_verified += 1
            continue

        scanned += 1
        candidates: list[dict[str, Any]] = []

        for evidence in proposal_evidence_rows:
            evidence_text = str(evidence.get("text") or "")
            if not evidence_text.strip():
                continue

            match_stub = {
                "requirement_id": req_id,
                "score": None,
                "evidence": dict(evidence),
            }
            response_role, role_flags, role_reason = (
                classify_response_evidence_role(req, match_stub)
            )
            entailment = response_entailment_signal(
                requirement_title=str(req.get("title") or ""),
                evidence_text=evidence_text,
            )
            entailment_status = str(
                entailment.get("entailment_status") or ""
            )
            candidate_class = _candidate_class(
                response_role=response_role,
                entailment_status=entailment_status,
            )
            retrieval = _retrieval_score(req, evidence_text)

            # Keep all supported candidates. Review candidates need at least some
            # retrieval signal so the CSV does not become a dump of every page.
            if (
                candidate_class == "RECOVERABLE_VERIFIED_RESPONSE_CANDIDATE"
                or (
                    candidate_class == "RECALL_REVIEW_CANDIDATE"
                    and retrieval >= 0.20
                )
            ):
                candidates.append({
                    "requirement_id": req_id,
                    "title": req.get("title"),
                    "requirement_type": req.get("requirement_type"),
                    "mandatory": req.get("mandatory"),
                    "priority": req.get("priority"),
                    "current_response_contract_status": current_status,
                    "candidate_class": candidate_class,
                    "retrieval_score": round(retrieval, 4),
                    "response_role": response_role,
                    "response_role_flags": " | ".join(role_flags),
                    "response_role_reason": role_reason,
                    "entailment_status": entailment_status,
                    "title_anchor_coverage":
                        entailment.get("title_anchor_coverage"),
                    "shared_title_tokens":
                        entailment.get("shared_title_tokens"),
                    "exact_title_phrase":
                        entailment.get("exact_title_phrase"),
                    "evidence_id": evidence.get("evidence_id"),
                    "evidence_source": evidence.get("source_name"),
                    "evidence_locator": evidence.get("locator_text"),
                    "evidence_text": evidence_text,
                })

        candidates.sort(
            key=lambda row: (
                0
                if row["candidate_class"]
                == "RECOVERABLE_VERIFIED_RESPONSE_CANDIDATE"
                else 1,
                -float(row.get("title_anchor_coverage") or 0.0),
                -float(row.get("retrieval_score") or 0.0),
                str(row.get("evidence_source") or "").casefold(),
                str(row.get("evidence_locator") or ""),
            )
        )

        accepted = [
            row
            for row in candidates
            if row["candidate_class"]
            == "RECOVERABLE_VERIFIED_RESPONSE_CANDIDATE"
        ]
        reviews = [
            row
            for row in candidates
            if row["candidate_class"]
            == "RECALL_REVIEW_CANDIDATE"
        ]

        if accepted:
            recoverable_requirements.add(req_id)
        elif reviews:
            review_requirements.add(req_id)
        else:
            no_candidate_requirements.add(req_id)

        top = candidates[: max(1, int(top_k))]
        if top:
            for rank, row in enumerate(top, start=1):
                detail.append({
                    **row,
                    "candidate_rank": rank,
                })
        else:
            detail.append({
                "requirement_id": req_id,
                "title": req.get("title"),
                "requirement_type": req.get("requirement_type"),
                "mandatory": req.get("mandatory"),
                "priority": req.get("priority"),
                "current_response_contract_status": current_status,
                "candidate_class": "NO_RECALL_CANDIDATE",
                "candidate_rank": None,
                "retrieval_score": None,
                "response_role": None,
                "response_role_flags": None,
                "response_role_reason": None,
                "entailment_status": None,
                "title_anchor_coverage": None,
                "shared_title_tokens": None,
                "exact_title_phrase": None,
                "evidence_id": None,
                "evidence_source": None,
                "evidence_locator": None,
                "evidence_text": None,
            })

    if recoverable_requirements:
        status = "PASS_WITH_RECOVERABLE_RECALL"
    elif review_requirements:
        status = "PASS_WITH_RECALL_REVIEW"
    else:
        status = "PASS_NO_SAFE_RECALL_FOUND"

    detail.sort(
        key=lambda row: (
            str(row.get("current_response_contract_status") or ""),
            str(row.get("title") or "").casefold(),
            int(row.get("candidate_rank") or 999),
        )
    )

    return ResponseRecallShadow(
        project_id=str(project_id),
        status=status,
        current_requirement_count=len(requirements),
        already_verified_response_count=already_verified,
        requirements_scanned_count=scanned,
        recoverable_verified_candidate_count=len(recoverable_requirements),
        review_candidate_count=len(review_requirements),
        no_candidate_count=len(no_candidate_requirements),
        detail_rows=tuple(detail),
    )


def _rows(response: Any) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in (getattr(response, "data", None) or [])
        if isinstance(row, Mapping)
    ]


def run_response_recall_shadow(
    client: Any,
    *,
    project_id: str,
) -> ResponseRecallShadow:
    from project_domain_reader import read_domain
    from project_workspace_db import fetch_project_workspace_snapshot

    contract = run_response_contract_canary(
        client,
        project_id=project_id,
    )

    domain_read = read_domain(
        client,
        project_id,
        "requirements",
        legacy_loader=lambda: [],
        audit=False,
    )
    if str(domain_read.read_mode) != "shadow_compare":
        raise RuntimeError(
            f"B2.8 BLOCKED: requirements read_mode={domain_read.read_mode}"
        )

    snapshot = fetch_project_workspace_snapshot(
        client,
        project_id=project_id,
    )
    evidence = _proposal_evidence(snapshot)

    return audit_response_recall(
        project_id=project_id,
        current_requirement_rows=[
            dict(row)
            for row in (domain_read.domain_candidate or [])
            if isinstance(row, Mapping)
        ],
        current_contract_rows=[
            dict(row) for row in contract.requirement_rows
        ],
        proposal_evidence_rows=evidence,
    )
