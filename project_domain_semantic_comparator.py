from __future__ import annotations

"""NAVE V28.7.3A3.1.1 — governance-aware Semantic Shadow Comparator.

The comparator explains *why* Legacy and Domain differ. It does not require row
count parity and never mutates truth/readiness/read_mode.

Classification vocabulary:
- same_semantics
- domain_more_precise
- expected_structural_difference
- legacy_only_unverified
- domain_only_evidence_led
- governed_feedback_context (explicitly reviewed as feedback, not Current Outcome)
- semantic_conflict
- review_required  (fail-closed ambiguity; blocks cutover until reviewed)
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
import re
import unicodedata
from typing import Any

COMPARATOR_VERSION = "V28.7.3A3.1.1"
COMPARISON_SCOPE = "v28.7.3a3_1_semantic_scope_compare"
STRUCTURAL_DOMAINS = {"context", "outcomes", "strategy", "creative", "experience", "journey"}
CLASSIFICATIONS = {
    "same_semantics",
    "domain_more_precise",
    "expected_structural_difference",
    "legacy_only_unverified",
    "domain_only_evidence_led",
    "expected_truth_correction",
    "governed_feedback_context",
    "semantic_conflict",
    "review_required",
}

_STOPWORDS = {
    "a", "ao", "aos", "as", "o", "os", "um", "uma", "uns", "umas",
    "de", "da", "das", "do", "dos", "e", "em", "no", "na", "nos", "nas",
    "para", "por", "com", "sem", "que", "ser", "ter", "se", "ou", "the",
    "and", "of", "to", "for", "in", "on", "project", "projeto", "item",
}

_TECHNICAL_KEYS = {
    "id", "project_id", "created_at", "updated_at", "source_asset_id",
    "evidence_unit_id", "resolved_domain_id", "canonical_entity_id", "run_id",
    "analysis_run_id", "raw_data", "attributes", "metadata",
}

_DOMAIN_TEXT_FIELDS = {
    "context": (
        "context_name", "element_name", "name", "title", "canonical_name",
        "observed_name", "description", "value", "context_type",
    ),
    "requirements": (
        "requirement_name", "canonical_name", "name", "title", "observed_text",
        "observed_name", "requirement_text", "description", "statement",
        "requirement_type", "semantic_role",
    ),
    "solutions": (
        "solution_name", "canonical_name", "name", "title", "observed_name",
        "description", "solution_type", "category", "status",
    ),
    "outcomes": (
        "outcome_type", "outcome_key", "outcome_name", "name", "title",
        "outcome_value", "outcome_status", "current_value", "value", "status", "state",
        "process_type", "commercial_result", "proposal_status", "execution_status",
        "proposal_result", "execution_result",
        "entity_name",
    ),
    "strategy": (
        "strategy_name", "element_name", "name", "title", "canonical_name",
        "observed_name", "statement", "description", "strategy_type",
    ),
    "creative": (
        "platform_name", "creative_name", "element_name", "name", "title",
        "canonical_name", "observed_name", "description", "creative_type",
    ),
    "experience": (
        "architecture_name", "experience_name", "name", "title", "canonical_name",
        "observed_name", "description", "architecture_type",
    ),
    "journey": (
        "moment_name", "journey_name", "stage_name", "name", "title",
        "canonical_name", "observed_name", "description", "stage", "phase",
    ),
}

_OUTCOME_DIMENSION_ALIASES = {
    "process_type": "process_type",
    "process": "process_type",
    "commercial_result": "commercial_result",
    "commercial": "commercial_result",
    "proposal_result": "proposal_status",
    "proposal_status": "proposal_status",
    "proposal": "proposal_status",
    "execution_result": "execution_status",
    "execution_status": "execution_status",
    "execution": "execution_status",
}

_OUTCOME_VALUE_GROUPS = {
    "process_type": {
        "competition", "direct", "proactive", "renewal", "not_applicable", "not_informed"
    },
    "commercial_result": {
        "in_evaluation", "won", "lost", "cancelled", "suspended", "no_return",
        "not_applicable", "not_informed"
    },
    "proposal_status": {
        "approved", "approved_with_changes", "rejected", "replaced", "cancelled",
        "unknown", "not_applicable"
    },
    "execution_status": {
        "executed", "partial", "not_executed", "planned", "not_applicable"
    },
}


@dataclass(frozen=True)
class SemanticComparisonItem:
    classification: str
    domain_key: str
    score: float
    domain_text: str | None
    legacy_text: str | None
    domain_id: str | None
    legacy_id: str | None
    legacy_source: str | None
    reason: str
    domain_subject: str | None = None
    legacy_subject: str | None = None
    domain_phase: str | None = None
    legacy_phase: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SemanticComparisonResult:
    domain_key: str
    semantic_status: str
    domain_row_count: int
    legacy_row_count: int
    classification_counts: dict[str, int]
    semantic_conflicts: int
    review_required: int
    items: list[SemanticComparisonItem]
    comparator_version: str = COMPARATOR_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain_key": self.domain_key,
            "semantic_status": self.semantic_status,
            "domain_row_count": self.domain_row_count,
            "legacy_row_count": self.legacy_row_count,
            "classification_counts": dict(self.classification_counts),
            "semantic_conflicts": self.semantic_conflicts,
            "review_required": self.review_required,
            "items": [item.to_dict() for item in self.items],
            "comparator_version": self.comparator_version,
        }


def _fold(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text.casefold())
    return re.sub(r"\s+", " ", text).strip()


def _tokens(value: Any) -> set[str]:
    tokens = {
        token
        for token in _fold(value).split()
        if len(token) >= 2 and token not in _STOPWORDS
    }
    variants = set(tokens)
    for token in tokens:
        if token.endswith("s") and len(token) > 4:
            variants.add(token[:-1])
    return variants


def _render(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, Mapping):
        parts = []
        for key, item in value.items():
            if key in _TECHNICAL_KEYS:
                continue
            rendered = _render(item)
            if rendered:
                parts.append(f"{key}: {rendered}")
        return " | ".join(parts)
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return "; ".join(filter(None, (_render(item) for item in value)))
    return str(value).strip()


def _row_text(row: Mapping[str, Any], domain_key: str, *, legacy: bool) -> str:
    if legacy:
        legacy_text = str(row.get("_legacy_text") or "").strip()
        if legacy_text:
            return legacy_text

    parts: list[str] = []
    seen: set[str] = set()
    for field in _DOMAIN_TEXT_FIELDS.get(domain_key, ("name", "title", "description")):
        rendered = _render(row.get(field))
        folded = _fold(rendered)
        if rendered and folded not in seen:
            seen.add(folded)
            parts.append(rendered)

    # Fail-safe fallback for schema drift: include a small set of meaningful
    # scalar values without polluting comparison text with ids/timestamps.
    if not parts:
        for key, value in row.items():
            if key in _TECHNICAL_KEYS or key.startswith("_"):
                continue
            if isinstance(value, (str, int, float)) and not isinstance(value, bool):
                rendered = str(value).strip()
                folded = _fold(rendered)
                if rendered and folded not in seen:
                    seen.add(folded)
                    parts.append(rendered)
    return " | ".join(parts)


def _row_id(row: Mapping[str, Any], *, legacy: bool) -> str | None:
    if legacy:
        value = row.get("_legacy_source_id") or row.get("id")
    else:
        value = row.get("id") or row.get("requirement_id") or row.get("entity_id")
    return str(value) if value else None


def _score(left: str, right: str) -> tuple[float, float, float, float]:
    a = _fold(left)
    b = _fold(right)
    if not a or not b:
        return 0.0, 0.0, 0.0, 0.0
    if a == b:
        return 1.0, 1.0, 1.0, 1.0

    ta = _tokens(a)
    tb = _tokens(b)
    intersection = ta & tb
    dice = (2 * len(intersection) / (len(ta) + len(tb))) if ta and tb else 0.0
    containment = (
        len(intersection) / min(len(ta), len(tb))
        if ta and tb
        else 0.0
    )
    sequence = SequenceMatcher(None, a, b).ratio()
    substring = 1.0 if (len(a) >= 4 and len(b) >= 4 and (a in b or b in a)) else 0.0

    score = min(1.0, dice * 0.48 + containment * 0.30 + sequence * 0.14 + substring * 0.18)
    return round(score, 4), round(dice, 4), round(containment, 4), round(sequence, 4)


def _domain_evidence_backed(row: Mapping[str, Any]) -> bool:
    truth_state = str(row.get("truth_state") or row.get("verification_state") or "").casefold()
    if truth_state in {"verified", "human_confirmed", "confirmed"}:
        return True
    if (
        row.get("evidence_unit_id")
        or row.get("source_asset_id")
        or row.get("source_evidence_id")
        or row.get("source_claim_id")
        or row.get("is_human_confirmed")
        or row.get("_semantic_evidence_backed")
    ):
        return True
    for key in ("evidence_count", "evidence_links", "current_evidence_count"):
        try:
            if int(row.get(key) or 0) > 0:
                return True
        except Exception:
            pass
    return False


def _outcome_dimension_value(row: Mapping[str, Any], *, legacy: bool) -> tuple[str | None, str | None]:
    if legacy:
        dimension = str(row.get("_legacy_outcome_dimension") or "").strip()
        value = str(row.get("_legacy_outcome_value") or "").strip()
        if dimension and value:
            return _OUTCOME_DIMENSION_ALIASES.get(dimension, dimension), _fold(value).replace(" ", "_")

    for dimension in _OUTCOME_VALUE_GROUPS:
        raw = row.get(dimension)
        if raw not in (None, ""):
            return dimension, _fold(raw).replace(" ", "_")

    dimension_raw = (
        row.get("outcome_type")
        or row.get("outcome_key")
        or row.get("outcome_name")
        or row.get("type")
    )
    value_raw = (
        row.get("outcome_status")
        or row.get("outcome_value")
        or row.get("current_value")
        or row.get("value")
        or row.get("state")
        or row.get("status")
    )
    dimension = _fold(dimension_raw).replace(" ", "_")
    value = _fold(value_raw).replace(" ", "_")
    if dimension in _OUTCOME_DIMENSION_ALIASES:
        dimension = _OUTCOME_DIMENSION_ALIASES[dimension]
    return (dimension or None, value or None)


def _outcome_conflict(domain_row: Mapping[str, Any], legacy_row: Mapping[str, Any]) -> bool:
    d_dim, d_val = _outcome_dimension_value(domain_row, legacy=False)
    l_dim, l_val = _outcome_dimension_value(legacy_row, legacy=True)
    if not d_dim or not l_dim or d_dim != l_dim or not d_val or not l_val:
        return False
    if d_val == l_val:
        return False
    # not_informed on either side is missing information, not a contradiction.
    if d_val in {"not_informed", "unknown", "none"} or l_val in {"not_informed", "unknown", "none"}:
        return False
    return True




def _subject_key(row: Mapping[str, Any]) -> str | None:
    value = str(row.get("_semantic_subject_key") or "").strip()
    return value or None


def _subject_phase(row: Mapping[str, Any]) -> str | None:
    value = str(row.get("_semantic_lifecycle_phase") or "").strip()
    return value or None


def _legacy_material_feedback(row: Mapping[str, Any]) -> bool:
    return bool(row.get("_semantic_material_feedback"))


def _legacy_governed_feedback_context(row: Mapping[str, Any]) -> bool:
    return bool(row.get("_semantic_governed_feedback_context"))


def _legacy_evidence_backed(row: Mapping[str, Any]) -> bool:
    return bool(row.get("_legacy_human_confirmed") or row.get("_semantic_evidence_backed"))


def _outcome_subjects_match(domain_row: Mapping[str, Any], legacy_row: Mapping[str, Any]) -> bool:
    d_subject = _subject_key(domain_row)
    l_subject = _subject_key(legacy_row)
    return bool(d_subject and l_subject and d_subject == l_subject)


def _identity_name(row: Mapping[str, Any], *, legacy: bool) -> str:
    fields = ("title", "name", "canonical_name", "solution_name", "observed_name") if legacy else (
        "solution_name", "canonical_name", "name", "title", "observed_name"
    )
    for field in fields:
        value = str(row.get(field) or "").strip()
        if value:
            return value
    return ""


def _domain_legacy_source_ids(row: Mapping[str, Any]) -> set[str]:
    values: set[str] = set()
    raw = row.get("legacy_source_ids")
    if isinstance(raw, str):
        if raw.strip():
            values.add(raw.strip())
    elif isinstance(raw, Sequence) and not isinstance(raw, (bytes, bytearray, str)):
        values.update(str(item) for item in raw if item)
    attributes = row.get("attributes") or {}
    if isinstance(attributes, Mapping):
        raw = attributes.get("legacy_memory_item_ids")
        if isinstance(raw, str):
            if raw.strip():
                values.add(raw.strip())
        elif isinstance(raw, Sequence) and not isinstance(raw, (bytes, bytearray, str)):
            values.update(str(item) for item in raw if item)
    return values


def _solution_identity_anchor(domain_row: Mapping[str, Any], legacy_row: Mapping[str, Any]) -> str | None:
    legacy_id = str(legacy_row.get("_legacy_source_id") or legacy_row.get("id") or "").strip()
    d_name = _fold(_identity_name(domain_row, legacy=False))
    l_name = _fold(_identity_name(legacy_row, legacy=True))
    if legacy_id and legacy_id in _domain_legacy_source_ids(domain_row):
        if d_name and l_name and d_name == l_name:
            return "legacy_source_id+exact_name"
        return "legacy_source_id"
    if d_name and l_name and d_name == l_name:
        return "exact_name"
    return None


def _legacy_project_execution_covered_by_domain(
    legacy_row: Mapping[str, Any],
    domain_rows: Sequence[Mapping[str, Any]],
) -> bool:
    if str(legacy_row.get("_semantic_subject_kind") or "") != "project":
        return False
    l_dim, l_val = _outcome_dimension_value(legacy_row, legacy=True)
    if l_dim != "execution_status" or not l_val:
        return False
    for row in domain_rows:
        if str(row.get("_semantic_subject_kind") or "") != "solution":
            continue
        d_dim, d_val = _outcome_dimension_value(row, legacy=False)
        if d_dim == l_dim and d_val == l_val and _domain_evidence_backed(row):
            return True
    return False


def _collective_overlap(text: str, rows: Sequence[Mapping[str, Any]], domain_key: str, *, legacy_rows: bool) -> float:
    base = _tokens(text)
    if not base:
        return 0.0
    collective: set[str] = set()
    for row in rows:
        collective.update(_tokens(_row_text(row, domain_key, legacy=legacy_rows)))
    return len(base & collective) / len(base) if base else 0.0


def compare_domain_candidates(
    domain_key: str,
    domain_rows: Sequence[Mapping[str, Any]],
    legacy_rows: Sequence[Mapping[str, Any]],
    *,
    domain_evidence_ready: bool = False,
) -> SemanticComparisonResult:
    """Explain semantic differences without assuming row-count parity."""
    domain_rows = [dict(row) for row in domain_rows if isinstance(row, Mapping)]
    legacy_rows = [dict(row) for row in legacy_rows if isinstance(row, Mapping)]

    # Empty is valid truth. It only becomes suspicious if a human-confirmed
    # legacy row disappears without a Domain counterpart.
    if not domain_rows and not legacy_rows:
        return SemanticComparisonResult(
            domain_key=domain_key,
            semantic_status="semantic_pass",
            domain_row_count=0,
            legacy_row_count=0,
            classification_counts={},
            semantic_conflicts=0,
            review_required=0,
            items=[],
        )

    domain_texts = [_row_text(row, domain_key, legacy=False) for row in domain_rows]
    legacy_texts = [_row_text(row, domain_key, legacy=True) for row in legacy_rows]

    # Greedy one-to-one pairing by strongest semantic score. Structural
    # one-to-many differences are recovered below through collective overlap.
    candidates: list[tuple[float, int, int, float, float, float]] = []
    for d_index, d_text in enumerate(domain_texts):
        for l_index, l_text in enumerate(legacy_texts):
            if domain_key == "outcomes":
                d_row = domain_rows[d_index]
                l_row = legacy_rows[l_index]
                if _legacy_governed_feedback_context(l_row):
                    # Explicit Human Review recategorized this legacy row as
                    # feedback context, not as a Current Outcome candidate.
                    continue
                d_dim, d_val = _outcome_dimension_value(d_row, legacy=False)
                l_dim, l_val = _outcome_dimension_value(l_row, legacy=True)
                # A3.1: categorical dimensions are comparable only for the SAME
                # semantic subject. A project outcome can never conflict with a
                # solution outcome merely because both use proposal_status.
                if (
                    not d_dim
                    or not l_dim
                    or d_dim != l_dim
                    or not _outcome_subjects_match(d_row, l_row)
                ):
                    continue
                if d_val and l_val and d_val == l_val:
                    score, dice, containment, sequence = 1.0, 1.0, 1.0, 1.0
                else:
                    lexical, dice, containment, sequence = _score(d_text, l_text)
                    score = max(0.90, lexical)
                candidates.append((score, d_index, l_index, dice, containment, sequence))
                continue

            score, dice, containment, sequence = _score(d_text, l_text)
            if domain_key == "solutions":
                anchor = _solution_identity_anchor(domain_rows[d_index], legacy_rows[l_index])
                if anchor == "legacy_source_id+exact_name":
                    score, dice, containment, sequence = 1.0, 1.0, 1.0, 1.0
                elif anchor == "exact_name":
                    score = max(score, 0.93)
                elif anchor == "legacy_source_id":
                    # Preserve lineage without blindly declaring semantic identity.
                    score = max(score, 0.70)
            if score >= 0.34:
                candidates.append((score, d_index, l_index, dice, containment, sequence))
    candidates.sort(reverse=True, key=lambda item: item[0])

    used_domain: set[int] = set()
    used_legacy: set[int] = set()
    items: list[SemanticComparisonItem] = []

    for score, d_index, l_index, dice, containment, sequence in candidates:
        if d_index in used_domain or l_index in used_legacy:
            continue
        d_row = domain_rows[d_index]
        l_row = legacy_rows[l_index]
        d_text = domain_texts[d_index]
        l_text = legacy_texts[l_index]

        if domain_key == "outcomes" and _outcome_conflict(d_row, l_row):
            d_phase = _subject_phase(d_row)
            l_phase = _subject_phase(l_row)
            if _legacy_material_feedback(l_row):
                classification = "review_required"
                reason = (
                    "same subject/dimension has a documented feedback-state disagreement; "
                    "treat as a possible lifecycle transition and reconcile explicitly before cutover"
                )
            elif _domain_evidence_backed(d_row) and not _legacy_evidence_backed(l_row):
                classification = "expected_truth_correction"
                reason = (
                    "same subject/dimension differs, but Domain is evidence-backed while Legacy "
                    "is unverified; preserve Legacy as recall without overriding current truth"
                )
            elif d_phase and l_phase and d_phase != l_phase:
                classification = "review_required"
                reason = (
                    f"same subject/dimension differs across lifecycle phases "
                    f"({d_phase} vs {l_phase}); ordering/current-state semantics require review"
                )
            elif _domain_evidence_backed(d_row) and _legacy_evidence_backed(l_row):
                classification = "semantic_conflict"
                reason = "same subject/dimension carries contradictory evidence-backed current values"
            else:
                classification = "review_required"
                reason = "same subject/dimension differs without enough provenance to declare a hard conflict"
        elif score >= 0.82:
            classification = "same_semantics"
            if domain_key == "solutions" and _solution_identity_anchor(d_row, l_row):
                reason = "same solution identity preserved by exact name and/or legacy source binding"
            else:
                reason = f"strong semantic equivalence (score={score:.2f})"
        elif score >= 0.60 and containment >= 0.64:
            classification = "domain_more_precise"
            reason = f"core meaning preserved with narrower/cleaner Domain wording (containment={containment:.2f})"
        elif domain_key in STRUCTURAL_DOMAINS and score >= 0.44:
            classification = "expected_structural_difference"
            reason = f"same semantic neighborhood represented with different granularity (score={score:.2f})"
        elif score >= 0.52:
            classification = "review_required"
            reason = f"partial overlap is too weak to auto-accept (score={score:.2f})"
        else:
            continue

        used_domain.add(d_index)
        used_legacy.add(l_index)
        items.append(
            SemanticComparisonItem(
                classification=classification,
                domain_key=domain_key,
                score=score,
                domain_text=d_text or None,
                legacy_text=l_text or None,
                domain_id=_row_id(d_row, legacy=False),
                legacy_id=_row_id(l_row, legacy=True),
                legacy_source=str(l_row.get("_legacy_source_table") or "") or None,
                reason=reason,
                domain_subject=_subject_key(d_row),
                legacy_subject=_subject_key(l_row),
                domain_phase=_subject_phase(d_row),
                legacy_phase=_subject_phase(l_row),
            )
        )

    unmatched_legacy = [row for index, row in enumerate(legacy_rows) if index not in used_legacy]
    unmatched_domain = [row for index, row in enumerate(domain_rows) if index not in used_domain]

    for row in unmatched_domain:
        text = _row_text(row, domain_key, legacy=False)
        structural_overlap = (
            0.0
            if domain_key == "outcomes"
            else _collective_overlap(text, legacy_rows, domain_key, legacy_rows=True)
        )
        evidence_backed = domain_evidence_ready or _domain_evidence_backed(row)
        if domain_key in STRUCTURAL_DOMAINS and domain_key != "outcomes" and structural_overlap >= 0.55:
            classification = "expected_structural_difference"
            reason = f"Domain atom is covered collectively by legacy container(s) (coverage={structural_overlap:.2f})"
        elif evidence_backed:
            classification = "domain_only_evidence_led"
            reason = "current Domain truth is evidence-ready but has no same-subject legacy row-level counterpart"
        else:
            classification = "review_required"
            reason = "Domain-only row lacks row-level evidence signal and could not be structurally explained"
        items.append(
            SemanticComparisonItem(
                classification=classification,
                domain_key=domain_key,
                score=round(structural_overlap, 4),
                domain_text=text or None,
                legacy_text=None,
                domain_id=_row_id(row, legacy=False),
                legacy_id=None,
                legacy_source=None,
                reason=reason,
                domain_subject=_subject_key(row),
                legacy_subject=None,
                domain_phase=_subject_phase(row),
                legacy_phase=None,
            )
        )

    for row in unmatched_legacy:
        text = _row_text(row, domain_key, legacy=True)
        structural_overlap = (
            0.0
            if domain_key == "outcomes"
            else _collective_overlap(text, domain_rows, domain_key, legacy_rows=False)
        )
        human_confirmed = bool(row.get("_legacy_human_confirmed"))
        if domain_key == "outcomes" and _legacy_governed_feedback_context(row):
            classification = "governed_feedback_context"
            reason = (
                "explicit Human Review recategorized this legacy item state as governed feedback "
                "context rather than a Current Outcome; preserve it as learning/recall without "
                "promoting it into outcome truth"
            )
        elif domain_key == "outcomes" and _legacy_material_feedback(row):
            classification = "review_required"
            reason = (
                "documented client-feedback outcome has no same-subject current Domain counterpart; "
                "it does not become truth by label alone, but must be reconciled before cutover"
            )
        elif domain_key == "outcomes" and _legacy_project_execution_covered_by_domain(row, domain_rows):
            classification = "expected_structural_difference"
            reason = "legacy project-level execution container is represented by evidence-backed solution execution outcomes"
        elif domain_key in STRUCTURAL_DOMAINS and domain_key != "outcomes" and structural_overlap >= 0.55:
            classification = "expected_structural_difference"
            reason = f"legacy container/atom is covered collectively by Domain representation (coverage={structural_overlap:.2f})"
        elif human_confirmed:
            classification = "review_required"
            reason = "human-confirmed legacy truth disappeared from Domain and requires explicit review"
        else:
            classification = "legacy_only_unverified"
            reason = "legacy recall has no same-subject current evidence-backed Domain counterpart"
        items.append(
            SemanticComparisonItem(
                classification=classification,
                domain_key=domain_key,
                score=round(structural_overlap, 4),
                domain_text=None,
                legacy_text=text or None,
                domain_id=None,
                legacy_id=_row_id(row, legacy=True),
                legacy_source=str(row.get("_legacy_source_table") or "") or None,
                reason=reason,
                domain_subject=None,
                legacy_subject=_subject_key(row),
                domain_phase=None,
                legacy_phase=_subject_phase(row),
            )
        )

    counts = Counter(item.classification for item in items)
    conflicts = int(counts.get("semantic_conflict", 0))
    review = int(counts.get("review_required", 0))
    status = "semantic_conflict" if conflicts else ("semantic_review" if review else "semantic_pass")

    return SemanticComparisonResult(
        domain_key=domain_key,
        semantic_status=status,
        domain_row_count=len(domain_rows),
        legacy_row_count=len(legacy_rows),
        classification_counts=dict(counts),
        semantic_conflicts=conflicts,
        review_required=review,
        items=items,
    )


def _clip(value: Any, limit: int = 360) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def semantic_audit_metadata(
    comparison: SemanticComparisonResult,
    *,
    legacy_adapter_version: str,
    semantic_scope_version: str | None = None,
) -> dict[str, Any]:
    details = []
    for item in comparison.items[:160]:
        details.append(
            {
                "classification": item.classification,
                "score": item.score,
                "domain_id": item.domain_id,
                "legacy_id": item.legacy_id,
                "legacy_source": item.legacy_source,
                "domain_subject": item.domain_subject,
                "legacy_subject": item.legacy_subject,
                "domain_phase": item.domain_phase,
                "legacy_phase": item.legacy_phase,
                "domain_text": _clip(item.domain_text),
                "legacy_text": _clip(item.legacy_text),
                "reason": _clip(item.reason, 260),
            }
        )
    return {
        "semantic_shadow": True,
        "semantic_status": comparison.semantic_status,
        "semantic_conflicts": comparison.semantic_conflicts,
        "review_required": comparison.review_required,
        "classification_counts": comparison.classification_counts,
        "comparator_version": comparison.comparator_version,
        "legacy_adapter_version": legacy_adapter_version,
        "semantic_scope_version": semantic_scope_version,
        "details": details,
    }


def persist_semantic_comparison_audit(
    client: Any,
    *,
    project_id: str,
    domain_key: str,
    read_mode: str,
    readiness_state: str,
    served_source: str,
    domain_row_count: int,
    legacy_row_count: int,
    fallback_used: bool,
    reader_version: str,
    comparison: SemanticComparisonResult,
    legacy_adapter_version: str,
    semantic_scope_version: str | None = None,
) -> None:
    """Persist A3.1 proof. Unlike optional runtime audit, failure blocks A3.1."""
    payload = {
        "project_id": project_id,
        "domain_key": domain_key,
        "read_mode": read_mode,
        "readiness_state": readiness_state,
        "served_source": served_source,
        "domain_row_count": domain_row_count,
        "legacy_row_count": legacy_row_count,
        "fallback_used": bool(fallback_used),
        "comparison_status": comparison.semantic_status,
        "reader_version": reader_version,
        "request_scope": COMPARISON_SCOPE,
        "metadata": semantic_audit_metadata(
            comparison,
            legacy_adapter_version=legacy_adapter_version,
            semantic_scope_version=semantic_scope_version,
        ),
    }
    try:
        client.table("project_domain_read_audit").insert(payload).execute()
    except Exception as exc:  # runtime integration path
        raise RuntimeError(
            f"Could not persist semantic comparison audit for {project_id}/{domain_key}: {exc}"
        ) from exc
