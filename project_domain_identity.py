from __future__ import annotations

"""NAVE V28.7.2A — conservative identity policy for Project Domain reconciliation.

This module intentionally does not reuse the V28.6 auto-merge policy. It may attach a
new evidence occurrence to one existing Project Solution Instance when the match is
unambiguous, but it never merges two existing domain identities automatically.
"""

import difflib
import re
import unicodedata
from typing import Any, Mapping, Sequence


def normalize_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _name_token(token: str) -> str:
    value = normalize_name(token)
    if value.endswith("ens") and len(value) > 5:
        value = value[:-3] + "em"
    elif value.endswith("s") and len(value) > 5:
        value = value[:-1]
    return value


def name_tokens(value: Any) -> set[str]:
    stop = {"de", "da", "do", "das", "dos", "e", "em", "para", "com", "por", "no", "na"}
    return {
        _name_token(token)
        for token in normalize_name(value).split()
        if token not in stop and len(token) >= 4
    }


def similarity(left: Any, right: Any) -> float:
    a = normalize_name(left)
    b = normalize_name(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    contains = 0.94 if a in b or b in a else 0.0
    sequence = difflib.SequenceMatcher(None, a, b).ratio()
    ta, tb = name_tokens(a), name_tokens(b)
    overlap = len(ta & tb) / max(len(ta | tb), 1)
    return max(contains, sequence, overlap)




_GENERIC_IDENTITY_TOKENS = {
    "ativacao", "activation",
    "solucao", "solution",
    "produto", "product",
    "brinde", "gift",
    "oficina", "workshop",
    "jogo", "game",
    "press", "item",
    "distribuicao", "distribution",
    "experiencia", "experience",
    "comunicacao", "communication",
    "conteudo", "content",
    "evento", "event",
    "jornada", "journey",
}


def _discriminative_tokens(value: Any) -> set[str]:
    return name_tokens(value) - _GENERIC_IDENTITY_TOKENS


def _identity_match_score(left: Any, right: Any) -> float:
    """Similarity for identity resolution, discounting domain-generic shared nouns.

    Character similarity can be misleading for templated labels such as
    ``TikTok activation`` vs ``Kwai activation``. When both sides have explicit
    non-generic anchors and those anchors are disjoint, shared generic words must
    not create a plausible identity match.
    """
    score = similarity(left, right)
    left_anchor = _discriminative_tokens(left)
    right_anchor = _discriminative_tokens(right)
    if left_anchor and right_anchor and left_anchor.isdisjoint(right_anchor):
        anchor_similarity = max(
            difflib.SequenceMatcher(None, left_token, right_token).ratio()
            for left_token in left_anchor
            for right_token in right_anchor
        )
        # Morphological variants (e.g. personalizada/personalização) may still be
        # plausible and must remain reviewable. Distinct anchors with low lexical
        # similarity (e.g. TikTok/Kwai) are not made plausible by the generic noun.
        if anchor_similarity < 0.70:
            return min(score, 0.55)
    return score


def _unique_anchor_match(name: str, solutions: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    candidate = name_tokens(name)
    if not candidate:
        return None
    solution_tokens = [(row, name_tokens(row.get("name"))) for row in solutions]

    subset_matches: list[Mapping[str, Any]] = []
    for row, tokens in solution_tokens:
        shared = candidate & tokens
        if not shared:
            continue
        if (candidate <= tokens or tokens <= candidate) and (len(shared) >= 2 or max(map(len, shared)) >= 7):
            subset_matches.append(row)
    if len(subset_matches) == 1:
        return subset_matches[0]

    generic = _GENERIC_IDENTITY_TOKENS
    frequency: dict[str, int] = {}
    for _row, tokens in solution_tokens:
        for token in tokens:
            frequency[token] = frequency.get(token, 0) + 1

    anchored: list[Mapping[str, Any]] = []
    for row, tokens in solution_tokens:
        anchors = {
            token for token in candidate & tokens
            if len(token) >= 7 and token not in generic and frequency.get(token) == 1
        }
        if anchors:
            anchored.append(row)
    return anchored[0] if len(anchored) == 1 else None


def resolve_observed_identity(name: str, solutions: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Return an action without mutating domain identity.

    Actions:
      - attach_existing: one existing identity is unambiguous;
      - review_required: there is plausible ambiguity, so creation/merge is blocked;
      - create_new: no plausible identity exists.
    """
    clean_name = str(name or "").strip()
    if not clean_name:
        return {"action": "review_required", "reason": "empty_name", "candidates": []}

    exact = [row for row in solutions if normalize_name(row.get("name")) == normalize_name(clean_name)]
    if len(exact) == 1:
        return {"action": "attach_existing", "target": dict(exact[0]), "score": 1.0, "reason": "exact_name"}
    if len(exact) > 1:
        return {"action": "review_required", "reason": "multiple_exact", "candidates": [dict(r) for r in exact]}

    scored = sorted(
        [(_identity_match_score(clean_name, row.get("name")), row) for row in solutions],
        key=lambda item: item[0], reverse=True,
    )
    best_score = scored[0][0] if scored else 0.0
    second_score = scored[1][0] if len(scored) > 1 else 0.0
    if scored and best_score >= 0.92 and (best_score - second_score) >= 0.08:
        return {
            "action": "attach_existing", "target": dict(scored[0][1]), "score": best_score,
            "reason": "strong_unique_similarity",
        }

    anchored = _unique_anchor_match(clean_name, solutions)
    if anchored is not None:
        return {"action": "attach_existing", "target": dict(anchored), "score": max(best_score, 0.86), "reason": "unique_anchor"}

    plausible = [dict(row) for score, row in scored if score >= 0.72]
    if plausible:
        return {
            "action": "review_required",
            "reason": "plausible_existing_identity",
            "score": best_score,
            "candidates": plausible[:4],
        }
    return {"action": "create_new", "reason": "no_plausible_existing_identity", "score": best_score}
