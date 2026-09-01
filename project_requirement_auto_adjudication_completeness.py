from __future__ import annotations

"""NAVE V28.7.3B2.12.2.2 — Completeness Quantifier Guard.

READ ONLY / shadow only.

This is a conservative wrapper over B2.12.2.1. It does not change Requirement Truth,
Human Review, persistence, read_mode, canaries or cutover. It only prevents a machine
`recommend_confirm` when the canonical obligation contains an unresolved completeness /
universal quantifier that the response evidence does not itself prove.

Example:
- Requirement: invitation + STD + reminder + "todo o material proposto no projeto"
- Evidence: Save the Date + invitation + reminder
The named atoms are covered, but the open-set "all proposed material" clause is not.
The safe machine recommendation is therefore PARTIAL, not CONFIRM.
"""

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Mapping, Sequence
import re
import unicodedata

from project_requirement_auto_adjudication_hardening import (
    run_semantic_hardened_adjudication as _run_b21221,
)

SEMANTIC_HARDENING_VERSION = "V28.7.3B2.12.2.2"

RECOMMEND_CONFIRM = "recommend_confirm"
RECOMMEND_PARTIAL = "recommend_partial"
RECOMMEND_REJECT = "recommend_reject"
RECOMMEND_VISUAL_REVIEW = "recommend_visual_review"
RECOMMEND_DEFER = "recommend_defer"


@dataclass(frozen=True)
class CompletenessHardenedAdjudication:
    project_id: str
    status: str
    current_requirement_count_before_semantic_gate: int
    semantic_eligible_requirement_count: int
    semantic_excluded_no_domain_count: int
    semantic_unknown_count: int
    canonical_identity_collision_count: int
    queue_count: int
    recommend_confirm_count: int
    recommend_partial_count: int
    recommend_reject_count: int
    recommend_visual_review_count: int
    recommend_defer_count: int
    completeness_downgrade_count: int
    recommendation_rows: tuple[dict[str, Any], ...]
    semantic_excluded_rows: tuple[dict[str, Any], ...]
    canonical_identity_collision_rows: tuple[dict[str, Any], ...]
    projection_rows: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SEMANTIC_HARDENING_VERSION,
            "base_version": "V28.7.3B2.12.2.1",
            "project_id": self.project_id,
            "status": self.status,
            "current_requirement_count_before_semantic_gate": self.current_requirement_count_before_semantic_gate,
            "semantic_eligible_requirement_count": self.semantic_eligible_requirement_count,
            "semantic_excluded_no_domain_count": self.semantic_excluded_no_domain_count,
            "semantic_unknown_count": self.semantic_unknown_count,
            "canonical_identity_collision_count": self.canonical_identity_collision_count,
            "queue_count": self.queue_count,
            "recommend_confirm_count": self.recommend_confirm_count,
            "recommend_partial_count": self.recommend_partial_count,
            "recommend_reject_count": self.recommend_reject_count,
            "recommend_visual_review_count": self.recommend_visual_review_count,
            "recommend_defer_count": self.recommend_defer_count,
            "completeness_downgrade_count": self.completeness_downgrade_count,
            "adjudicator_type": "machine_rule_engine_semantic_hardening_completeness_guard",
            "human_review_created": False,
            "truth_changed": False,
            "persistence_performed": False,
            "cutover_approved": False,
            "recommendation_rows": list(self.recommendation_rows),
            "semantic_excluded_rows": list(self.semantic_excluded_rows),
            "canonical_identity_collision_rows": list(self.canonical_identity_collision_rows),
            "projection_rows": list(self.projection_rows),
        }


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9$+]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _segments(text: str) -> list[str]:
    output: list[str] = []
    for line in re.split(r"[\r\n]+", str(text or "")):
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            continue
        for part in re.split(r"(?<=[.!?;])\s+", line):
            part = re.sub(r"\s+", " ", part).strip(" \t•·-")
            if part:
                output.append(part)
    return output


_COMPLETENESS_MARKERS = (
    "todo", "toda", "todos", "todas",
    "integralmente", "por completo", "completo", "completa", "completos", "completas",
    "all", "every", "entire", "entirely", "complete", "completely", "in full", "full set",
)

_SCOPE_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "materials",
        (
            r"\btod[oa]s?\s+(?:os?\s+|as?\s+)?materia(?:l|is)\b",
            r"\btod[oa]s?\s+(?:os?\s+|as?\s+)?pecas?\b",
            r"\btod[oa]s?\s+(?:os?\s+|as?\s+)?itens?\b",
            r"\ball\s+(?:proposed\s+)?materials?\b",
            r"\ball\s+(?:proposed\s+)?assets?\b",
            r"\ball\s+items?\b",
            r"\bentire\s+(?:material|asset)\s+set\b",
        ),
    ),
    (
        "universal_guests",
        (
            r"\btodos?\s+(?:os?\s+)?convidados?\b",
            r"\btodas?\s+(?:as?\s+)?pessoas\b",
            r"\ball\s+guests?\b",
            r"\bevery\s+guest\b",
        ),
    ),
    (
        "full_kit",
        (
            r"\btodo\s+(?:o\s+)?kit\b",
            r"\bkit\s+completo\b",
            r"\btodos?\s+(?:os?\s+)?acessorios?\b",
            r"\bcomplete\s+kit\b",
            r"\bfull\s+kit\b",
            r"\ball\s+accessories\b",
        ),
    ),
    (
        "integral_completeness",
        (
            r"\bintegralmente\b",
            r"\bpor\s+completo\b",
            r"\bentirely\b",
            r"\bin\s+full\b",
        ),
    ),
)

_SCOPE_EVIDENCE_TERMS: dict[str, tuple[str, ...]] = {
    "materials": (
        "material", "materiais", "peça", "peca", "peças", "pecas", "item", "itens",
        "asset", "assets", "material", "materials", "communication", "communications",
    ),
    "universal_guests": ("guest", "guests", "convidado", "convidados", "pessoa", "pessoas"),
    "full_kit": ("kit", "acessorio", "acessorios", "accessory", "accessories"),
    "integral_completeness": (),
}


def _completeness_scope(requirement_text: str) -> str | None:
    n = _norm(requirement_text)
    for scope, patterns in _SCOPE_PATTERNS:
        if any(re.search(pattern, n, flags=re.I) for pattern in patterns):
            return scope
    return None


def _contains_marker(text: str) -> bool:
    n = f" {_norm(text)} "
    return any(f" {_norm(marker)} " in n for marker in _COMPLETENESS_MARKERS)


def _evidence_proves_completeness(scope: str, evidence_text: str) -> bool:
    terms = _SCOPE_EVIDENCE_TERMS.get(scope, ())
    for segment in _segments(evidence_text):
        if not _contains_marker(segment):
            continue
        if not terms:
            return True
        n = f" {_norm(segment)} "
        if any(f" {_norm(term)} " in n for term in terms):
            return True
    return False


def _candidate_id(source_candidate_id: str, project_id: str, requirement_id: str) -> str:
    payload = "|".join([
        str(source_candidate_id or ""),
        str(project_id or ""),
        str(requirement_id or ""),
        SEMANTIC_HARDENING_VERSION,
    ])
    return sha256(payload.encode("utf-8")).hexdigest()[:24]


def apply_completeness_guard(base: Any) -> CompletenessHardenedAdjudication:
    recommendations: list[dict[str, Any]] = []
    downgrades = 0

    for raw in tuple(base.recommendation_rows):
        row = dict(raw)
        source_candidate_id = str(row.get("candidate_id") or "")
        canonical = str(row.get("canonical_obligation_text") or row.get("requirement_title") or "")
        evidence = str(row.get("evidence_text") or "")
        scope = _completeness_scope(canonical)

        row["source_candidate_id"] = source_candidate_id or None
        row["candidate_id"] = _candidate_id(
            source_candidate_id,
            str(row.get("project_id") or base.project_id),
            str(row.get("requirement_id") or ""),
        )
        row["source_projection_version"] = "V28.7.3B2.11/B2.12.2.2 projection"
        row["source_atom_gate_version"] = (
            "V28.7.3B2.10.2.2 canonical+hard-qualifier+completeness recalibration"
        )
        row["adjudicator_type"] = "machine_rule_engine_semantic_hardening_completeness_guard"
        row["completeness_scope"] = scope
        row["completeness_guard_applied"] = False

        if (
            row.get("machine_recommendation") == RECOMMEND_CONFIRM
            and scope
            and not _evidence_proves_completeness(scope, evidence)
        ):
            row.update({
                "machine_recommendation": RECOMMEND_PARTIAL,
                "machine_confidence": 0.96,
                "machine_rule_id": "unresolved_completeness_quantifier",
                "machine_rationale": (
                    "A evidência cobre itens explícitos da obrigação, mas não comprova "
                    "a abrangência total/universal exigida pelo texto canônico."
                ),
                "completeness_guard_applied": True,
            })
            downgrades += 1

        row["human_review_created"] = False
        row["truth_effect_applied"] = False
        row["persistence_performed"] = False
        recommendations.append(row)

    counts = {
        RECOMMEND_CONFIRM: 0,
        RECOMMEND_PARTIAL: 0,
        RECOMMEND_REJECT: 0,
        RECOMMEND_VISUAL_REVIEW: 0,
        RECOMMEND_DEFER: 0,
    }
    for row in recommendations:
        key = str(row.get("machine_recommendation") or RECOMMEND_DEFER)
        counts[key] = counts.get(key, 0) + 1

    recommendations.sort(
        key=lambda row: (
            0 if row.get("machine_recommendation") == RECOMMEND_CONFIRM else
            1 if row.get("machine_recommendation") == RECOMMEND_PARTIAL else
            2 if row.get("machine_recommendation") == RECOMMEND_VISUAL_REVIEW else
            3 if row.get("machine_recommendation") == RECOMMEND_DEFER else 4,
            -float(row.get("machine_confidence") or 0),
            str(row.get("requirement_title") or "").casefold(),
        )
    )

    return CompletenessHardenedAdjudication(
        project_id=str(base.project_id),
        status=str(base.status),
        current_requirement_count_before_semantic_gate=int(base.current_requirement_count_before_semantic_gate),
        semantic_eligible_requirement_count=int(base.semantic_eligible_requirement_count),
        semantic_excluded_no_domain_count=int(base.semantic_excluded_no_domain_count),
        semantic_unknown_count=int(base.semantic_unknown_count),
        canonical_identity_collision_count=int(base.canonical_identity_collision_count),
        queue_count=len(recommendations),
        recommend_confirm_count=counts[RECOMMEND_CONFIRM],
        recommend_partial_count=counts[RECOMMEND_PARTIAL],
        recommend_reject_count=counts[RECOMMEND_REJECT],
        recommend_visual_review_count=counts[RECOMMEND_VISUAL_REVIEW],
        recommend_defer_count=counts[RECOMMEND_DEFER],
        completeness_downgrade_count=downgrades,
        recommendation_rows=tuple(recommendations),
        semantic_excluded_rows=tuple(dict(row) for row in base.semantic_excluded_rows),
        canonical_identity_collision_rows=tuple(
            dict(row) for row in base.canonical_identity_collision_rows
        ),
        projection_rows=tuple(dict(row) for row in base.projection_rows),
    )


def run_semantic_hardened_adjudication(
    client: Any,
    *,
    project_id: str,
) -> CompletenessHardenedAdjudication:
    """Run B2.12.2.2. Underlying B2.12.2.1 remains read-only; wrapper only downgrades."""
    base = _run_b21221(client, project_id=project_id)
    return apply_completeness_guard(base)
