from __future__ import annotations

"""NAVE V28.7.2C0.2.4 — conservative Project Requirement identity policy.

Requirement identity is not string dedup. C0.2.4 makes evidence-first binding stricter:
- explicit lineage is authoritative;
- exact current title is safe;
- evidence-first semantic attachment uses title compatibility first, never a broad shared
  Evidence description by itself;
- abstract constraint identities may use description support only inside the same
  constraint family;
- two existing identities are never auto-merged.
"""

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any, Mapping, Sequence


GENERIC_REQUIREMENT_TOKENS = {
    "requisito", "requirement", "objetivo", "objective", "diretriz", "diretrizes",
    "guideline", "guidelines", "deve", "devera", "deverá", "devem", "precisa", "precisam",
    "necessario", "necessaria", "must", "should", "criar", "create", "desenvolver", "develop",
    "garantir", "ensure", "entregar", "deliver", "considerar", "apresentar", "incluir", "para",
    "com", "sem", "the", "and", "with", "for", "evento", "proposta", "agencia", "agências",
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
    if raw in {"budget", "orcamento", "constraint", "restricao", "restriction"}:
        return "constraint"
    if raw in {"deliverable", "entrega", "channel", "canal", "platform", "plataforma"}:
        return "delivery"
    if raw in {"operation", "operacao", "logistica", "logistics"}:
        return "operation"
    if raw in {"deadline", "prazo", "timing", "timming", "date", "data"}:
        return "deadline"
    if raw in {"objective", "objetivo"}:
        return "objective"
    if raw in {"requirement", "requisito", "mandatory", "obrigatorio", "obrigatoria"}:
        return "other"
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
    return max(containment, 0.62 * token_score + 0.38 * seq)


def _compatible_type(observed_type: Any, row_type: Any) -> bool:
    left = _type_family(observed_type)
    right = _type_family(row_type)
    return left in {"", "other"} or right in {"", "other"} or left == right


def resolve_requirement_identity(
    observation: Mapping[str, Any],
    existing_requirements: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Resolve one current evidence-backed Requirement observation conservatively.

    Evidence-first clauses may not attach to an unrelated existing identity merely because
    both clauses were extracted from the same large Evidence Unit. Description similarity
    is therefore disallowed for normal evidence-first binding.
    """
    rows = [dict(row) for row in existing_requirements]
    attrs = observation.get("attributes") if isinstance(observation.get("attributes"), Mapping) else {}
    legacy_id = str(attrs.get("legacy_requirement_id") or "")
    domain_id = str(attrs.get("requirement_id") or "")
    origin_route = str(attrs.get("origin_route") or "")

    # Route 1 — explicit lineage. This is identity, not fuzzy matching.
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

    # Route 2 — exact title. Safe on both legacy-recall and evidence-first.
    exact = [row for row in rows if normalize_requirement_text(row.get("title")) == norm and norm]
    if len(exact) == 1:
        return {"action": "attach_existing", "target": exact[0], "reason": "exact_requirement_title", "score": 1.0}
    if len(exact) > 1:
        return {"action": "review_required", "candidates": exact, "reason": "duplicate_existing_requirement_titles", "score": 1.0}

    observed_type = _type_family(observation.get("observed_type"))
    scored: list[tuple[float, dict[str, Any], str]] = []

    for row in rows:
        if not _compatible_type(observation.get("observed_type"), row.get("requirement_type")):
            continue

        title_score = _similarity(name, row.get("title"))
        score = title_score
        basis = "title"

        # Exception: abstract constraint labels such as "Restrição de verba e estrutura"
        # legitimately summarize a longer current Evidence clause. This exception is
        # limited to the constraint family so that shared evidence prose cannot bind
        # unrelated deliverables (the MC/timing bug proven by JOVI).
        row_type = _type_family(row.get("requirement_type"))
        if observed_type == "constraint" and row_type == "constraint":
            description_score = _similarity(name, row.get("description"))
            if description_score > score:
                score = description_score
                basis = "constraint_description"

        if score >= 0.80:
            scored.append((score, row, basis))

    scored.sort(key=lambda item: -item[0])

    if origin_route == "evidence_first":
        # Evidence-first attaches automatically only on a materially strong unique title
        # match (or the narrow constraint exception above). Moderate resemblance means the
        # clause is a new identity; it is safer to create than to cross-bind two facts.
        strong = [item for item in scored if item[0] >= (0.86 if item[2] == "constraint_description" else 0.90)]
        if len(strong) == 1:
            return {"action": "attach_existing", "target": strong[0][1], "reason": f"evidence_first_{strong[0][2]}_match", "score": strong[0][0]}
        if len(strong) > 1:
            lead = strong[0][0]
            close = [row for score, row, _basis in strong if lead - score <= 0.05]
            if len(close) > 1:
                return {"action": "review_required", "candidates": close, "reason": "multiple_strong_requirement_identities", "score": lead}
            return {"action": "attach_existing", "target": strong[0][1], "reason": f"dominant_evidence_first_{strong[0][2]}_match", "score": lead}
        return {"action": "create_new", "reason": "no_strong_evidence_first_identity_match", "score": scored[0][0] if scored else 0.0}

    # Legacy-recall without explicit lineage should remain conservative.
    if len(scored) == 1:
        if scored[0][0] >= 0.88:
            return {"action": "attach_existing", "target": scored[0][1], "reason": "unique_semantic_requirement_match", "score": scored[0][0]}
        return {"action": "review_required", "candidates": [scored[0][1]], "reason": "plausible_requirement_identity_needs_review", "score": scored[0][0]}
    if len(scored) > 1:
        lead = scored[0][0]
        close = [row for score, row, _basis in scored if lead - score <= 0.08]
        if len(close) > 1 or lead < 0.88:
            return {"action": "review_required", "candidates": close or [scored[0][1]], "reason": "multiple_plausible_requirement_identities", "score": lead}
        return {"action": "attach_existing", "target": scored[0][1], "reason": "dominant_semantic_requirement_match", "score": lead}

    return {"action": "create_new", "reason": "no_plausible_existing_requirement", "score": 0.0}
