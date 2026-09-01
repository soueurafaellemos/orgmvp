from __future__ import annotations

"""NAVE V28.7.3B2.12.3 — Canonical Requirement Identity Collision Resolution Shadow.

READ ONLY / shadow only.

Purpose:
- detect two or more Current Requirement identities that resolve to the exact same
  source-bounded canonical obligation;
- produce a deterministic, provenance-aware resolution PLAN;
- never merge, supersede, rebind, delete, write Truth, create Human Review or cut over.

A future transactional phase may consume only plans explicitly marked
`ready_for_transactional_resolution`, after Golden validation.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Sequence
import re
import unicodedata

from project_requirement_semantic_eligibility import resolve_requirement_semantics

COLLISION_SHADOW_VERSION = "V28.7.3B2.12.3"

CURRENT_TRUTH_STATES = {"verified", "human_confirmed"}
ELIGIBLE_ROLES = {"requirement_candidate", "constraint_candidate"}


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, Mapping):
        return [dict(data)]
    return [dict(row) for row in (data or []) if isinstance(row, Mapping)]


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _attrs(row: Mapping[str, Any]) -> Mapping[str, Any]:
    value = row.get("attributes")
    return value if isinstance(value, Mapping) else {}


def _id(row: Mapping[str, Any]) -> str:
    return str(row.get("id") or row.get("requirement_id") or "")


def _title(row: Mapping[str, Any]) -> str:
    return str(
        row.get("title")
        or row.get("requirement_name")
        or row.get("canonical_name")
        or ""
    ).strip()


def _truth(row: Mapping[str, Any]) -> str:
    return str(
        row.get("truth_state")
        or row.get("verification_state")
        or row.get("truth_status")
        or ""
    ).casefold()


def _bool_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return None
    text = str(value).strip().casefold()
    if text in {"true", "t", "1", "yes", "sim"}:
        return True
    if text in {"false", "f", "0", "no", "nao", "não"}:
        return False
    return None


def _origin(row: Mapping[str, Any]) -> str:
    attrs = _attrs(row)
    origin = str(attrs.get("origin") or attrs.get("normalized_by") or "").casefold()
    if "evidence_led" in origin or "evidence-first" in origin or "evidence_first" in origin:
        return "evidence_led"
    if row.get("legacy_source_id"):
        return "legacy_mirror"
    if "legacy" in origin:
        return "legacy_mirror"
    return "unknown"


def _title_is_truncated(title: str, canonical: str) -> bool:
    nt, nc = _norm(title), _norm(canonical)
    if not nt or not nc or nt == nc:
        return False
    if len(nt) < len(nc) and nc.startswith(nt):
        return (len(nc) - len(nt)) >= 12
    # common UI/source hard truncation: final token is a prefix of canonical next token
    tt, ct = nt.split(), nc.split()
    if len(tt) >= 4 and len(tt) <= len(ct):
        prefix = ct[:len(tt)]
        if tt[:-1] == prefix[:-1] and prefix[-1].startswith(tt[-1]):
            return len(nc) - len(nt) >= 8
    return False


def _metadata_conflicts(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    conflicts: list[str] = []

    mandatory = {
        value
        for row in rows
        if (value := _bool_or_none(row.get("mandatory"))) is not None
    }
    if len(mandatory) > 1:
        conflicts.append("mandatory")

    types = {
        _norm(row.get("requirement_type"))
        for row in rows
        if _norm(row.get("requirement_type"))
    }
    if len(types) > 1:
        conflicts.append("requirement_type")

    priorities = {
        _norm(row.get("priority"))
        for row in rows
        if _norm(row.get("priority")) and _norm(row.get("priority")) != "not informed"
    }
    if len(priorities) > 1:
        conflicts.append("priority")

    return conflicts


def _identity_score(
    row: Mapping[str, Any],
    *,
    occurrence_count: int,
) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []

    truth = _truth(row)
    if truth == "human_confirmed":
        score += 100
        reasons.append("human_confirmed")

    origin = _origin(row)
    if origin == "evidence_led":
        score += 40
        reasons.append("evidence_led_identity")
    elif origin == "legacy_mirror":
        score += 10
        reasons.append("legacy_lineage_preserved")

    source = str(row.get("canonical_obligation_source") or "")
    if source == "semantic_observation.source_atom":
        score += 30
        reasons.append("source_atom_canonical")
    elif source == "current_evidence.source_clause":
        score += 20
        reasons.append("source_clause_canonical")
    elif source == "display_title":
        reasons.append("display_title_only")

    canonical = str(row.get("canonical_obligation_text") or "")
    title = _title(row)
    if title and canonical and not _title_is_truncated(title, canonical):
        score += 10
        reasons.append("non_truncated_title")
    elif _title_is_truncated(title, canonical):
        reasons.append("truncated_title")

    confidence = float(row.get("canonical_obligation_confidence") or 0.0)
    if confidence >= 0.995:
        score += 8
        reasons.append("canonical_confidence_very_high")
    elif confidence >= 0.99:
        score += 5
        reasons.append("canonical_confidence_high")

    if occurrence_count:
        score += min(10, int(occurrence_count))
        reasons.append(f"active_occurrences:{int(occurrence_count)}")

    return score, reasons


@dataclass(frozen=True)
class CollisionResolutionPlan:
    canonical_obligation_key: str
    canonical_obligation_text: str
    requirement_ids: tuple[str, ...]
    resolution_status: str
    proposed_survivor_id: str | None
    proposed_superseded_ids: tuple[str, ...]
    metadata_conflicts: tuple[str, ...]
    survivor_score: int | None
    score_margin: int | None
    occurrence_rebind_count: int
    legacy_alias_rebind_count: int
    exact_canonical_match: bool
    auto_merge_performed: bool = False
    persistence_performed: bool = False
    truth_changed: bool = False
    cutover_approved: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_obligation_key": self.canonical_obligation_key,
            "canonical_obligation_text": self.canonical_obligation_text,
            "requirement_ids": list(self.requirement_ids),
            "resolution_status": self.resolution_status,
            "proposed_survivor_id": self.proposed_survivor_id,
            "proposed_superseded_ids": list(self.proposed_superseded_ids),
            "metadata_conflicts": list(self.metadata_conflicts),
            "survivor_score": self.survivor_score,
            "score_margin": self.score_margin,
            "occurrence_rebind_count": self.occurrence_rebind_count,
            "legacy_alias_rebind_count": self.legacy_alias_rebind_count,
            "exact_canonical_match": self.exact_canonical_match,
            "auto_merge_performed": self.auto_merge_performed,
            "persistence_performed": self.persistence_performed,
            "truth_changed": self.truth_changed,
            "cutover_approved": self.cutover_approved,
        }


@dataclass(frozen=True)
class IdentityCollisionShadowReport:
    project_id: str
    current_requirement_count: int
    semantic_eligible_count: int
    collision_count: int
    ready_collision_count: int
    review_required_count: int
    blocked_collision_count: int
    plans: tuple[CollisionResolutionPlan, ...]
    identity_audit_rows: tuple[dict[str, Any], ...]

    @property
    def status(self) -> str:
        if self.blocked_collision_count:
            return "BLOCKED_COLLISION_INTEGRITY"
        if self.review_required_count:
            return "REVIEW_REQUIRED_IDENTITY_COLLISION"
        if self.collision_count:
            return "PASS_SHADOW_READY_FOR_TRANSACTIONAL_DESIGN"
        return "PASS_NO_CANONICAL_IDENTITY_COLLISIONS"

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": COLLISION_SHADOW_VERSION,
            "project_id": self.project_id,
            "status": self.status,
            "current_requirement_count": self.current_requirement_count,
            "semantic_eligible_count": self.semantic_eligible_count,
            "collision_count": self.collision_count,
            "ready_collision_count": self.ready_collision_count,
            "review_required_count": self.review_required_count,
            "blocked_collision_count": self.blocked_collision_count,
            "auto_merge_performed": False,
            "persistence_performed": False,
            "truth_changed": False,
            "human_review_created": False,
            "cutover_approved": False,
            "plans": [plan.to_dict() for plan in self.plans],
            "identity_audit_rows": list(self.identity_audit_rows),
        }


def build_identity_collision_shadow_from_rows(
    *,
    project_id: str,
    eligible_rows: Sequence[Mapping[str, Any]],
    occurrence_rows: Sequence[Mapping[str, Any]],
    raw_requirement_rows: Sequence[Mapping[str, Any]] = (),
    current_requirement_count: int | None = None,
) -> IdentityCollisionShadowReport:
    raw_by_id = {_id(row): dict(row) for row in raw_requirement_rows if _id(row)}

    occurrences_by_requirement: dict[str, list[dict[str, Any]]] = {}
    legacy_aliases_by_requirement: dict[str, set[str]] = {}
    for raw in occurrence_rows:
        row = dict(raw)
        if str(row.get("lifecycle_status") or "active").casefold() != "active":
            continue
        rid = str(row.get("requirement_id") or "")
        if not rid:
            continue
        occurrences_by_requirement.setdefault(rid, []).append(row)
        legacy_id = str(row.get("legacy_requirement_id") or "")
        if legacy_id:
            legacy_aliases_by_requirement.setdefault(rid, set()).add(legacy_id)

    enriched: list[dict[str, Any]] = []
    for raw in eligible_rows:
        row = {**raw_by_id.get(_id(raw), {}), **dict(raw)}
        rid = _id(row)
        canonical = str(row.get("canonical_obligation_text") or "").strip()
        key = _norm(canonical)
        if not rid or not key:
            continue
        row["canonical_obligation_key"] = key
        row["identity_origin"] = _origin(row)
        row["title_truncated_against_canonical"] = _title_is_truncated(_title(row), canonical)
        row["active_occurrence_count"] = len(occurrences_by_requirement.get(rid, []))
        aliases = set(legacy_aliases_by_requirement.get(rid, set()))
        if row.get("legacy_source_id"):
            aliases.add(str(row["legacy_source_id"]))
        row["legacy_aliases"] = sorted(aliases)
        score, reasons = _identity_score(
            row,
            occurrence_count=row["active_occurrence_count"],
        )
        row["survivor_score"] = score
        row["survivor_score_reasons"] = reasons
        enriched.append(row)

    groups: dict[str, list[dict[str, Any]]] = {}
    for row in enriched:
        groups.setdefault(str(row["canonical_obligation_key"]), []).append(row)

    plans: list[CollisionResolutionPlan] = []
    audit_rows: list[dict[str, Any]] = []
    ready = review = blocked = 0

    for key, rows in sorted(groups.items()):
        if len({str(row.get("id") or row.get("requirement_id") or "") for row in rows}) <= 1:
            continue

        ids = sorted({_id(row) for row in rows})
        canonical_texts = {
            _norm(row.get("canonical_obligation_text"))
            for row in rows
            if _norm(row.get("canonical_obligation_text"))
        }
        exact = len(canonical_texts) == 1

        for row in rows:
            audit_rows.append({
                "canonical_obligation_key": key,
                "requirement_id": _id(row),
                "title": _title(row),
                "canonical_obligation_text": row.get("canonical_obligation_text"),
                "canonical_obligation_source": row.get("canonical_obligation_source"),
                "canonical_obligation_confidence": row.get("canonical_obligation_confidence"),
                "semantic_role_current": row.get("semantic_role_current"),
                "truth_state": row.get("truth_state") or row.get("verification_state"),
                "identity_origin": row.get("identity_origin"),
                "legacy_source_id": row.get("legacy_source_id"),
                "mandatory": row.get("mandatory"),
                "requirement_type": row.get("requirement_type"),
                "priority": row.get("priority"),
                "title_truncated_against_canonical": row.get("title_truncated_against_canonical"),
                "active_occurrence_count": row.get("active_occurrence_count"),
                "legacy_aliases": row.get("legacy_aliases"),
                "survivor_score": row.get("survivor_score"),
                "survivor_score_reasons": row.get("survivor_score_reasons"),
            })

        metadata_conflicts = _metadata_conflicts(rows)

        # Identity safety gates.
        roles = {str(row.get("semantic_role_current") or "") for row in rows}
        if not exact or not roles.issubset(ELIGIBLE_ROLES):
            status = "blocked_non_exact_or_semantically_ineligible_collision"
            proposed = None
            superseded: tuple[str, ...] = ()
            survivor_score = margin = None
            blocked += 1
        else:
            ranked = sorted(
                rows,
                key=lambda row: (
                    -int(row.get("survivor_score") or 0),
                    _id(row),
                ),
            )
            lead = int(ranked[0].get("survivor_score") or 0)
            second = int(ranked[1].get("survivor_score") or 0)
            margin = lead - second

            human_ids = [
                _id(row) for row in rows if _truth(row) == "human_confirmed"
            ]
            if len(human_ids) > 1:
                status = "review_required_multiple_human_confirmed_identities"
                proposed = None
                superseded = ()
                survivor_score = None
                review += 1
            elif len(human_ids) == 1:
                proposed = human_ids[0]
                superseded = tuple(rid for rid in ids if rid != proposed)
                survivor_score = next(
                    int(row.get("survivor_score") or 0)
                    for row in rows if _id(row) == proposed
                )
                status = "ready_for_transactional_resolution"
                ready += 1
            elif margin >= 15 and lead >= 50:
                proposed = _id(ranked[0])
                superseded = tuple(rid for rid in ids if rid != proposed)
                survivor_score = lead
                status = "ready_for_transactional_resolution"
                ready += 1
            else:
                proposed = None
                superseded = ()
                survivor_score = lead
                status = "review_required_insufficient_provenance_margin"
                review += 1

        occurrence_rebind = sum(
            len(occurrences_by_requirement.get(rid, []))
            for rid in (superseded if proposed else ())
        )
        alias_rebind = sum(
            len(legacy_aliases_by_requirement.get(rid, set()))
            for rid in (superseded if proposed else ())
        )

        plans.append(CollisionResolutionPlan(
            canonical_obligation_key=key,
            canonical_obligation_text=str(rows[0].get("canonical_obligation_text") or ""),
            requirement_ids=tuple(ids),
            resolution_status=status,
            proposed_survivor_id=proposed,
            proposed_superseded_ids=superseded,
            metadata_conflicts=tuple(metadata_conflicts),
            survivor_score=survivor_score,
            score_margin=margin if "margin" in locals() else None,
            occurrence_rebind_count=occurrence_rebind,
            legacy_alias_rebind_count=alias_rebind,
            exact_canonical_match=exact,
        ))
        if "margin" in locals():
            del margin

    eligible_count = len(tuple(eligible_rows))
    return IdentityCollisionShadowReport(
        project_id=str(project_id),
        current_requirement_count=(
            int(current_requirement_count)
            if current_requirement_count is not None
            else eligible_count
        ),
        semantic_eligible_count=eligible_count,
        collision_count=len(plans),
        ready_collision_count=ready,
        review_required_count=review,
        blocked_collision_count=blocked,
        plans=tuple(plans),
        identity_audit_rows=tuple(audit_rows),
    )


def run_identity_collision_shadow(
    client: Any,
    *,
    project_id: str,
) -> IdentityCollisionShadowReport:
    """Read current Requirement Truth and produce a collision-resolution plan. No writes."""
    truth_rows = _rows(
        client.table("project_requirement_truth_status")
        .select("*")
        .eq("project_id", project_id)
        .execute()
    )
    current = [
        row for row in truth_rows
        if _truth(row) in CURRENT_TRUTH_STATES
    ]

    semantics = resolve_requirement_semantics(
        client,
        project_id=project_id,
        current_requirement_rows=current,
    )

    raw_requirements = _rows(
        client.table("project_requirements")
        .select("*")
        .eq("project_id", project_id)
        .execute()
    )
    occurrences = _rows(
        client.table("project_requirement_occurrences")
        .select("*")
        .eq("project_id", project_id)
        .execute()
    )

    return build_identity_collision_shadow_from_rows(
        project_id=project_id,
        eligible_rows=semantics.eligible_rows,
        occurrence_rows=occurrences,
        raw_requirement_rows=raw_requirements,
        current_requirement_count=len(current),
    )
