from __future__ import annotations

"""NAVE V28.7.2C0 — conservative Project Requirement identity policy.

Requirement identity is not a string-dedup problem. The resolver prefers explicit
legacy/domain lineage and only attaches by text when there is one unambiguous,
semantically compatible candidate. Two existing requirements are never auto-merged.
"""

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any, Mapping, Sequence


GENERIC_REQUIREMENT_TOKENS = {
    "requisito", "requirement", "objetivo", "objective", "diretriz", "diretrizes",
    "guideline", "guidelines", "deve", "devera", "precisa", "necessario", "necessaria",
    "must", "should", "criar", "create", "desenvolver", "develop", "garantir", "ensure",
    "entregar", "deliver", "para", "com", "sem", "the", "and", "with", "for",
}


def normalize_requirement_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokens(value: Any) -> set[str]:
    return {
        token for token in normalize_requirement_text(value).split()
        if len(token) >= 2 and token not in GENERIC_REQUIREMENT_TOKENS
    }


def _type_family(value: Any) -> str:
    raw = normalize_requirement_text(value).replace(" ", "_")
    if raw in {"audience", "publico", "publico_alvo", "target_audience", "context", "contexto"}:
        return "context"
    if raw in {"budget", "orcamento", "constraint", "restricao"}:
        return "constraint"
    if raw in {"deliverable", "entrega", "channel", "canal", "platform", "plataforma"}:
        return "delivery"
    if raw in {"objective", "objetivo"}:
        return "objective"
    return raw or "other"


def _similarity(left: Any, right: Any) -> float:
    a = normalize_requirement_text(left)
    b = normalize_requirement_text(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    ta, tb = _tokens(a), _tokens(b)
    token_score = len(ta & tb) / max(1, len(ta | tb)) if (ta or tb) else 0.0
    seq = SequenceMatcher(None, a, b).ratio()
    containment = 0.92 if (len(a) >= 8 and a in b) or (len(b) >= 8 and b in a) else 0.0
    return max(containment, 0.58 * token_score + 0.42 * seq)


def resolve_requirement_identity(
    observation: Mapping[str, Any],
    existing_requirements: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Resolve one evidence-backed requirement observation conservatively.

    Order:
      1. explicit legacy/domain lineage => attach the same existing requirement;
      2. exact title => attach if unique;
      3. one high-score compatible candidate => attach;
      4. several plausible candidates => review_required;
      5. otherwise create_new (planner still applies a separate evidence gate).
    """
    rows = [dict(row) for row in existing_requirements]
    attrs = observation.get("attributes") if isinstance(observation.get("attributes"), Mapping) else {}
    legacy_id = str(attrs.get("legacy_requirement_id") or "")
    domain_id = str(attrs.get("requirement_id") or "")

    if domain_id:
        matches = [row for row in rows if str(row.get("id") or "") == domain_id]
        if len(matches) == 1:
            return {"action": "attach_existing", "target": matches[0], "reason": "explicit_requirement_id", "score": 1.0}

    if legacy_id:
        matches = [
            row for row in rows
            if str(row.get("legacy_source_id") or "") == legacy_id
            or str(row.get("id") or "") == legacy_id
        ]
        if len(matches) == 1:
            return {"action": "attach_existing", "target": matches[0], "reason": "legacy_lineage_same_requirement", "score": 1.0}
        if len(matches) > 1:
            return {"action": "review_required", "candidates": matches, "reason": "ambiguous_legacy_lineage", "score": 1.0}

    name = str(observation.get("observed_name") or "").strip()
    norm = normalize_requirement_text(name)
    exact = [row for row in rows if normalize_requirement_text(row.get("title")) == norm and norm]
    if len(exact) == 1:
        return {"action": "attach_existing", "target": exact[0], "reason": "exact_requirement_title", "score": 1.0}
    if len(exact) > 1:
        return {"action": "review_required", "candidates": exact, "reason": "duplicate_existing_requirement_titles", "score": 1.0}

    observed_type = _type_family(observation.get("observed_type"))
    scored: list[tuple[float, dict[str, Any]]] = []
    for row in rows:
        row_type = _type_family(row.get("requirement_type"))
        compatible = observed_type in {"", "other"} or row_type in {"", "other"} or observed_type == row_type
        if not compatible:
            continue
        score = max(
            _similarity(name, row.get("title")),
            _similarity(name, row.get("description")),
        )
        # A moderate semantic resemblance is enough to block silent creation, but
        # not enough to attach. This is deliberately asymmetric: ambiguity opens a
        # review; only a materially stronger unique match can attach automatically.
        if score >= 0.74:
            scored.append((score, row))

    scored.sort(key=lambda item: -item[0])
    if len(scored) == 1:
        if scored[0][0] >= 0.84:
            return {"action": "attach_existing", "target": scored[0][1], "reason": "unique_semantic_requirement_match", "score": scored[0][0]}
        return {"action": "review_required", "candidates": [scored[0][1]], "reason": "plausible_requirement_identity_needs_review", "score": scored[0][0]}
    if len(scored) > 1:
        lead = scored[0][0]
        close = [row for score, row in scored if lead - score <= 0.08]
        if len(close) > 1 or lead < 0.84:
            return {"action": "review_required", "candidates": close or [scored[0][1]], "reason": "multiple_plausible_requirement_identities", "score": lead}
        return {"action": "attach_existing", "target": scored[0][1], "reason": "dominant_semantic_requirement_match", "score": lead}

    return {"action": "create_new", "reason": "no_plausible_existing_requirement", "score": 0.0}
