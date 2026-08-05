from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any


STOP_WORDS = {
    "a",
    "as",
    "ao",
    "aos",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "em",
    "na",
    "nas",
    "no",
    "nos",
    "o",
    "os",
    "para",
    "por",
    "the",
    "by",
}

LEGAL_SUFFIXES = {
    "eireli",
    "ltda",
    "me",
    "sa",
    "s",
    "a",
}


def normalize_match_name(value: Any) -> str:
    text = unicodedata.normalize(
        "NFKD",
        str(value or ""),
    )
    text = "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )
    text = text.casefold()
    text = text.replace("&", " e ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def name_tokens(value: Any) -> list[str]:
    normalized = normalize_match_name(value)
    tokens = [
        token
        for token in normalized.split()
        if token
        and token not in STOP_WORDS
        and token not in LEGAL_SUFFIXES
    ]
    return tokens


def _sequence_score(
    first: str,
    second: str,
) -> float:
    if not first or not second:
        return 0.0

    return SequenceMatcher(
        None,
        first,
        second,
    ).ratio()


def _token_jaccard(
    first_tokens: set[str],
    second_tokens: set[str],
) -> float:
    if not first_tokens or not second_tokens:
        return 0.0

    union = first_tokens | second_tokens
    if not union:
        return 0.0

    return len(
        first_tokens & second_tokens
    ) / len(union)


def _token_containment(
    first_tokens: set[str],
    second_tokens: set[str],
) -> float:
    if not first_tokens or not second_tokens:
        return 0.0

    smaller = min(
        (first_tokens, second_tokens),
        key=len,
    )
    larger = max(
        (first_tokens, second_tokens),
        key=len,
    )

    if len(smaller) < 2:
        return 0.0

    coverage = len(smaller & larger) / len(smaller)

    if coverage >= 1.0:
        return 0.97

    if coverage >= 0.8:
        return 0.92

    return coverage * 0.85


def name_similarity(
    first: Any,
    second: Any,
) -> float:
    first_normalized = normalize_match_name(first)
    second_normalized = normalize_match_name(second)

    if not first_normalized or not second_normalized:
        return 0.0

    if first_normalized == second_normalized:
        return 1.0

    first_tokens = set(name_tokens(first))
    second_tokens = set(name_tokens(second))

    token_sort_first = " ".join(
        sorted(first_tokens)
    )
    token_sort_second = " ".join(
        sorted(second_tokens)
    )

    direct = _sequence_score(
        first_normalized,
        second_normalized,
    )
    token_sort = _sequence_score(
        token_sort_first,
        token_sort_second,
    )
    jaccard = _token_jaccard(
        first_tokens,
        second_tokens,
    )
    containment = _token_containment(
        first_tokens,
        second_tokens,
    )

    score = max(
        direct,
        token_sort,
        jaccard * 0.94,
        containment,
    )
    return round(min(score, 1.0), 4)


def _normalized_equal(
    first: Any,
    second: Any,
) -> bool:
    first_normalized = normalize_match_name(first)
    second_normalized = normalize_match_name(second)

    return bool(
        first_normalized
        and first_normalized == second_normalized
    )


def _same_or_blank(
    first: Any,
    second: Any,
) -> bool:
    if not first or not second:
        return True

    return _normalized_equal(first, second)


def product_candidate_score(
    incoming: dict,
    candidate: dict,
) -> float:
    incoming_sku = str(
        incoming.get("sku") or ""
    ).strip()
    candidate_sku = str(
        candidate.get("sku") or ""
    ).strip()

    if (
        incoming_sku
        and candidate_sku
        and normalize_match_name(incoming_sku)
        != normalize_match_name(candidate_sku)
    ):
        return 0.0

    score = name_similarity(
        incoming.get("name"),
        candidate.get("name"),
    )

    incoming_category = incoming.get("category")
    candidate_category = candidate.get("category")

    if (
        incoming_category
        and candidate_category
        and not _normalized_equal(
            incoming_category,
            candidate_category,
        )
    ):
        score -= 0.05

    return round(max(score, 0.0), 4)


def activation_candidate_score(
    incoming: dict,
    candidate: dict,
) -> float:
    if not _same_or_blank(
        incoming.get("project_name"),
        candidate.get("project_name"),
    ):
        return 0.0

    score = name_similarity(
        incoming.get("name"),
        candidate.get("name"),
    )

    incoming_category = incoming.get("category")
    candidate_category = candidate.get("category")

    if (
        incoming_category
        and candidate_category
        and not _normalized_equal(
            incoming_category,
            candidate_category,
        )
    ):
        score -= 0.04

    return round(max(score, 0.0), 4)


def venue_candidate_score(
    incoming: dict,
    candidate: dict,
) -> float:
    if not _same_or_blank(
        incoming.get("city"),
        candidate.get("city"),
    ):
        return 0.0

    score = name_similarity(
        incoming.get("name"),
        candidate.get("name"),
    )

    incoming_type = incoming.get("venue_type")
    candidate_type = candidate.get("venue_type")

    if (
        incoming_type
        and candidate_type
        and not _normalized_equal(
            incoming_type,
            candidate_type,
        )
    ):
        score -= 0.03

    return round(max(score, 0.0), 4)


MATCH_CONFIG = {
    "product": {
        "auto_threshold": 0.985,
        "review_threshold": 0.84,
        "score_function": product_candidate_score,
    },
    "activation": {
        "auto_threshold": 0.965,
        "review_threshold": 0.84,
        "score_function": activation_candidate_score,
    },
    "venue": {
        "auto_threshold": 0.94,
        "review_threshold": 0.78,
        "score_function": venue_candidate_score,
    },
}


def best_candidate_match(
    entity_type: str,
    incoming: dict,
    candidates: list[dict],
) -> dict:
    config = MATCH_CONFIG[entity_type]
    score_function = config["score_function"]

    ranked = []

    for candidate in candidates:
        score = score_function(
            incoming,
            candidate,
        )
        if score <= 0:
            continue

        ranked.append(
            {
                "candidate": candidate,
                "score": score,
            }
        )

    if not ranked:
        return {
            "decision": "none",
            "candidate": None,
            "score": 0.0,
            "method": "no_similar_candidate",
        }

    ranked.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    best = ranked[0]
    second_score = (
        ranked[1]["score"]
        if len(ranked) > 1
        else 0.0
    )

    score = float(best["score"])
    margin = score - second_score

    incoming_name = normalize_match_name(
        incoming.get("name")
    )
    candidate_name = normalize_match_name(
        best["candidate"].get("name")
    )

    if incoming_name == candidate_name:
        return {
            "decision": "auto",
            "candidate": best["candidate"],
            "score": 1.0,
            "method": "normalized_name",
        }

    if (
        score >= config["auto_threshold"]
        and margin >= 0.025
    ):
        return {
            "decision": "auto",
            "candidate": best["candidate"],
            "score": score,
            "method": "high_confidence_similarity",
        }

    if score >= config["review_threshold"]:
        return {
            "decision": "review",
            "candidate": best["candidate"],
            "score": score,
            "method": "possible_duplicate",
        }

    return {
        "decision": "none",
        "candidate": None,
        "score": score,
        "method": "low_similarity",
    }
