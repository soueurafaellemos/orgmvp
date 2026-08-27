from __future__ import annotations

"""NAVE V28.7.3B2.6 — Unified Response Entailment Shadow.

READ ONLY / shadow only.

B2.5 established semantic ownership, but ownership does not prove that a matched
proposal excerpt actually answers a requirement. This phase audits semantic
support between the requirement label and the retained response evidence.

Key rule:
    governed identity + material source role != proof of response entailment.

The audit is intentionally conservative and diagnostic. It never removes a
production match, changes thresholds, rewrites Truth, or creates aliases.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Sequence
import re

from project_requirement_unified_semantic_ownership_shadow import (
    build_semantic_ownership_shadow,
)

RESPONSE_ENTAILMENT_VERSION = 'V28.7.3B2.6'

_HIGH_RISK_DISPOSITIONS = {
    'requirement_owned_response',
    'domain_requirement_response_candidate',
}


def _norm(value: Any) -> str:
    from project_intelligence_unified import _norm as prod_norm
    return prod_norm(value)


def _distinctive_tokens(value: Any) -> set[str]:
    from project_intelligence_unified import _distinctive_tokens
    return set(_distinctive_tokens(value))


def _token_count(value: Any) -> int:
    from project_intelligence_unified import _tokens
    return len(_tokens(value))


def _exact_phrase(title: str, evidence_text: str) -> bool:
    title_norm = _norm(title).strip(' ;:,.')
    evidence_norm = _norm(evidence_text)
    if not title_norm or not evidence_norm:
        return False
    return bool(re.search(rf'\\b{re.escape(title_norm)}\\b', evidence_norm))


def response_entailment_signal(
    *,
    requirement_title: str,
    evidence_text: str,
) -> dict[str, Any]:
    """Conservative lexical-semantic support signal.

    This is NOT an entailment model. It is a deterministic false-positive screen
    designed to catch cases where the current matcher found a long-description
    overlap but the evidence does not even support the canonical requirement
    label, or where the evidence is only a section heading.
    """
    title = str(requirement_title or '').strip()
    evidence = str(evidence_text or '').strip()
    title_tokens = _distinctive_tokens(title)
    evidence_tokens = _distinctive_tokens(evidence)
    shared = title_tokens & evidence_tokens

    coverage = len(shared) / max(1, len(title_tokens)) if title_tokens else 0.0
    evidence_token_count = _token_count(evidence)
    exact = _exact_phrase(title, evidence)
    heading_like = evidence_token_count <= 4 and len(evidence) <= 80

    # A short, explicit semantic atom such as "Reels" or "Brindes" can be valid
    # even with a single token, provided the evidence is not merely a heading.
    short_atom = len(title_tokens) <= 2 and bool(shared)

    if not title_tokens:
        status = 'REVIEW_NO_CANONICAL_ANCHORS'
        reason = 'canonical title has no distinctive semantic anchors'
    elif not shared:
        status = 'REVIEW_NO_TITLE_ANCHOR'
        reason = 'material evidence shares no distinctive token with canonical requirement title'
    elif heading_like:
        status = 'REVIEW_HEADING_ONLY'
        reason = 'evidence is too short/heading-like to prove a substantive response'
    elif short_atom and (exact or coverage >= 0.5):
        status = 'SUPPORTED_EXPLICIT_ATOM'
        reason = 'short canonical semantic atom is explicitly present in substantive evidence'
    elif coverage >= 0.50 and len(shared) >= 2:
        status = 'SUPPORTED_CANONICAL_ANCHORS'
        reason = 'substantive evidence covers at least half of canonical title anchors'
    elif coverage >= 0.34 and len(shared) >= 2:
        status = 'REVIEW_PARTIAL_CANONICAL_SUPPORT'
        reason = 'substantive evidence has partial canonical support but not enough for automatic acceptance'
    else:
        status = 'REVIEW_WEAK_CANONICAL_SUPPORT'
        reason = 'substantive evidence has weak support for the canonical requirement label'

    return {
        'entailment_status': status,
        'entailment_reason': reason,
        'title_anchor_count': len(title_tokens),
        'shared_anchor_count': len(shared),
        'title_anchor_coverage': round(coverage, 4),
        'shared_title_tokens': ' | '.join(sorted(shared)),
        'evidence_token_count': evidence_token_count,
        'exact_title_phrase': exact,
        'heading_like_evidence': heading_like,
    }


@dataclass(frozen=True)
class ResponseEntailmentAudit:
    project_id: str
    status: str
    audited_response_count: int
    supported_count: int
    review_count: int
    hard_blocker_count: int
    ownership_review_count: int
    detail_rows: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            'version': RESPONSE_ENTAILMENT_VERSION,
            'project_id': self.project_id,
            'status': self.status,
            'audited_response_count': self.audited_response_count,
            'supported_count': self.supported_count,
            'review_count': self.review_count,
            'hard_blocker_count': self.hard_blocker_count,
            'ownership_review_count': self.ownership_review_count,
            'detail_rows': list(self.detail_rows),
        }


def audit_response_entailment_from_ownership(
    *,
    project_id: str,
    ownership_result: Any,
) -> ResponseEntailmentAudit:
    rows: list[dict[str, Any]] = []
    supported = 0
    review = 0
    hard = 0
    ownership_review = 0

    for raw in ownership_result.detail_rows:
        row = dict(raw)
        disposition = str(row.get('contract_disposition') or '')
        side = str(row.get('side') or '')

        # Non-response rows were already excluded correctly by B2.5.
        if disposition.endswith('non_response_excluded'):
            continue

        # Audit one canonical representation for governed requirement pairs:
        # Legacy side owns the compatibility identity. Domain-side duplicates are
        # not counted again. Domain-only response candidates remain auditable.
        if side == 'domain' and disposition == 'domain_requirement_response_candidate':
            domain_id = row.get('domain_requirement_id')
            duplicate_legacy = any(
                str(other.get('side') or '') == 'legacy'
                and str(other.get('domain_requirement_id') or '') == str(domain_id or '')
                and str(other.get('contract_disposition') or '') in {
                    'requirement_owned_response',
                    'mapped_requirement_response_asymmetry',
                }
                for other in ownership_result.detail_rows
            )
            if duplicate_legacy:
                continue

        if disposition not in {
            'requirement_owned_response',
            'mapped_requirement_response_asymmetry',
            'domain_requirement_response_candidate',
            'cross_domain_owned_same_evidence',
            'cross_domain_candidate_review',
            'material_response_component_unowned',
            'material_response_unowned',
        }:
            continue

        title = str(row.get('legacy_title') or row.get('domain_title') or '')
        evidence_text = str(row.get('evidence_text') or '')
        signal = response_entailment_signal(
            requirement_title=title,
            evidence_text=evidence_text,
        )
        ent_status = str(signal['entailment_status'])
        ent_supported = ent_status.startswith('SUPPORTED_')
        ent_review = not ent_supported

        # High blocker only when NAVE is currently claiming a requirement response
        # through governed/current requirement identity but canonical semantics are
        # not actually supported by the selected evidence.
        is_hard = (
            disposition in _HIGH_RISK_DISPOSITIONS
            and ent_status in {
                'REVIEW_NO_TITLE_ANCHOR',
                'REVIEW_HEADING_ONLY',
                'REVIEW_NO_CANONICAL_ANCHORS',
            }
        )

        if ent_supported:
            supported += 1
        else:
            review += 1
        if is_hard:
            hard += 1
        if bool(row.get('review_required')):
            ownership_review += 1

        rows.append({
            'side': side,
            'legacy_requirement_id': row.get('legacy_requirement_id'),
            'legacy_title': row.get('legacy_title'),
            'domain_requirement_id': row.get('domain_requirement_id'),
            'domain_title': row.get('domain_title'),
            'contract_disposition': disposition,
            'ownership_domain': row.get('ownership_domain'),
            'ownership_labels': row.get('ownership_labels'),
            'ownership_basis': row.get('ownership_basis'),
            'ownership_review_required': bool(row.get('review_required')),
            'match_score': row.get('match_score'),
            'evidence_id': row.get('evidence_id'),
            'evidence_locator': row.get('evidence_locator'),
            'evidence_text': evidence_text,
            **signal,
            'hard_blocker': is_hard,
        })

    if hard:
        status = 'BLOCKED_RESPONSE_EVIDENCE_FALSE_POSITIVE_RISK'
    elif review or ownership_review:
        status = 'PASS_WITH_RESPONSE_REVIEW'
    else:
        status = 'PASS_PROJECTED_RESPONSE_ENTAILMENT'

    rows.sort(key=lambda r: (
        not bool(r.get('hard_blocker')),
        str(r.get('entailment_status') or ''),
        str(r.get('legacy_title') or r.get('domain_title') or '').casefold(),
    ))

    return ResponseEntailmentAudit(
        project_id=str(project_id),
        status=status,
        audited_response_count=len(rows),
        supported_count=supported,
        review_count=review,
        hard_blocker_count=hard,
        ownership_review_count=ownership_review,
        detail_rows=tuple(rows),
    )


def run_response_entailment_shadow(client: Any, *, project_id: str) -> ResponseEntailmentAudit:
    from project_requirement_unified_semantic_ownership_shadow import (
        run_semantic_ownership_shadow,
    )

    ownership = run_semantic_ownership_shadow(client, project_id=project_id)
    if ownership.status == 'BLOCKED_MAPPED_RESPONSE_ASYMMETRY':
        raise RuntimeError(
            'B2.6 BLOCKED: B2.5 already found mapped response asymmetry.'
        )

    return audit_response_entailment_from_ownership(
        project_id=project_id,
        ownership_result=ownership,
    )
