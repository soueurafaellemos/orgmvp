from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Any
from urllib.parse import urlparse

from taxonomy import match_taxonomy, taxonomy_catalog_rows


STOP_WORDS = {
    "a", "as", "ao", "aos", "da", "das", "de", "do", "dos",
    "e", "em", "na", "nas", "no", "nos", "o", "os", "para",
    "por", "the", "by", "com", "sem", "uma", "um", "of", "and",
}

LEGAL_SUFFIXES = {
    "eireli", "ltda", "me", "sa", "s", "a", "inc", "llc",
}

# Terms that describe a commercial/taxonomic family, but do not identify the
# entity by themselves. The researched NAVE taxonomy is added to this set at
# runtime so aliases such as "caneca", "pavilhão" and "photo-op" do not create
# false duplicates merely because two records belong to the same family.
BASE_GENERIC_TOKENS = {
    "product": {
        "brinde", "brindes", "personalizado", "personalizada",
        "personalizados", "custom", "premium", "modelo", "linha",
    },
    "activation": {
        "ativacao", "ativacoes", "experiencia", "experiencias", "evento",
        "eventos", "solucao", "solucoes", "projeto", "acao", "acoes",
    },
    "venue": {
        "espaco", "espacos", "local", "locais", "eventos", "evento",
        "casa", "centro", "complexo", "unidade", "sao", "paulo",
    },
}

SUBSPACE_TOKENS = {
    "pavimento", "andar", "terreo", "subsolo", "mezanino", "sala",
    "salas", "salao", "saloes", "auditorio", "auditorios", "foyer",
    "pavilhao", "pavilhoes", "arena", "lounge", "hall", "rooftop",
    "terraco", "jardim", "deck", "area", "areas", "externa", "externo",
    "interna", "interno", "palco", "estudio", "estudios", "teatro",
    "galeria", "galerias", "restaurante", "bar", "quadra", "campo",
    "bloco", "torre", "ala", "anexo", "expansao", "planta",
}

ENTITY_CATEGORY_DIMENSION = {
    "product": "product_category",
    "venue": "venue_type",
    "activation": None,
}


def normalize_match_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(
        character for character in text
        if not unicodedata.combining(character)
    )
    text = text.casefold().replace("&", " e ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def name_tokens(value: Any) -> list[str]:
    return [
        token for token in normalize_match_name(value).split()
        if token and token not in STOP_WORDS and token not in LEGAL_SUFFIXES
    ]


@lru_cache(maxsize=8)
def _taxonomy_generic_tokens(entity_type: str) -> frozenset[str]:
    tokens = set(BASE_GENERIC_TOKENS.get(entity_type, set()))
    for row in taxonomy_catalog_rows():
        if str(row.get("entity_type") or "") != entity_type:
            continue
        dimension = str(row.get("dimension") or "")
        # Every term in these dimensions describes a family, type, mechanic or
        # attribute. It is useful for compatibility, but not an identity token.
        if entity_type == "product" and dimension != "product_category":
            continue
        if entity_type == "venue" and dimension not in {
            "venue_type", "venue_attribute"
        }:
            continue
        tokens.update(name_tokens(row.get("canonical_term")))
        tokens.update(name_tokens(row.get("alias")))
    return frozenset(tokens)


def distinctive_tokens(value: Any, entity_type: str) -> set[str]:
    generic = _taxonomy_generic_tokens(entity_type)
    return {
        token for token in name_tokens(value)
        if token not in generic and len(token) >= 2
    }


def _sequence_score(first: str, second: str) -> float:
    if not first or not second:
        return 0.0
    return SequenceMatcher(None, first, second).ratio()


def _jaccard(first: set[str], second: set[str]) -> float:
    if not first or not second:
        return 0.0
    union = first | second
    return len(first & second) / len(union) if union else 0.0


def _containment(first: set[str], second: set[str]) -> float:
    if not first or not second:
        return 0.0
    return len(first & second) / min(len(first), len(second))


def _normalized_equal(first: Any, second: Any) -> bool:
    first_normalized = normalize_match_name(first)
    second_normalized = normalize_match_name(second)
    return bool(first_normalized and first_normalized == second_normalized)


def _same_or_blank(first: Any, second: Any) -> bool:
    if not first or not second:
        return True
    return _normalized_equal(first, second)


def _clean_identifier(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalize_match_name(value))


def _domain(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if "://" not in text:
        text = f"https://{text}"
    try:
        host = (urlparse(text).hostname or "").casefold()
    except Exception:
        return ""
    return host.removeprefix("www.")


def _normalized_address(value: Any) -> str:
    text = normalize_match_name(value)
    return re.sub(
        r"\b(rua|r|avenida|av|estrada|estr|rodovia|rod|numero|n)\b",
        " ",
        text,
    ).strip()


def _canonical_category(record: dict, entity_type: str) -> str:
    field = "venue_type" if entity_type == "venue" else "category"
    value = record.get(field)
    if not value:
        return ""
    match = match_taxonomy(
        value,
        entity_type,
        dimension=ENTITY_CATEGORY_DIMENSION.get(entity_type),
        allow_fuzzy=False,
    )
    return normalize_match_name(match["canonical"] if match else value)


def _taxonomy_state(
    incoming: dict,
    candidate: dict,
    entity_type: str,
) -> tuple[str, str, str]:
    first = _canonical_category(incoming, entity_type)
    second = _canonical_category(candidate, entity_type)
    if first and second:
        return ("same" if first == second else "different", first, second)
    return ("unknown", first, second)


def _name_features(incoming: dict, candidate: dict, entity_type: str) -> dict:
    incoming_name = normalize_match_name(incoming.get("name"))
    candidate_name = normalize_match_name(candidate.get("name"))
    incoming_all = set(name_tokens(incoming_name))
    candidate_all = set(name_tokens(candidate_name))
    incoming_distinctive = distinctive_tokens(incoming_name, entity_type)
    candidate_distinctive = distinctive_tokens(candidate_name, entity_type)
    common_distinctive = incoming_distinctive & candidate_distinctive
    return {
        "incoming_name": incoming_name,
        "candidate_name": candidate_name,
        "exact_name": bool(incoming_name and incoming_name == candidate_name),
        "all_common": sorted(incoming_all & candidate_all),
        "incoming_distinctive": sorted(incoming_distinctive),
        "candidate_distinctive": sorted(candidate_distinctive),
        "common_distinctive": sorted(common_distinctive),
        "distinctive_jaccard": _jaccard(incoming_distinctive, candidate_distinctive),
        "distinctive_containment": _containment(
            incoming_distinctive, candidate_distinctive
        ),
        "distinctive_sequence": _sequence_score(
            " ".join(sorted(incoming_distinctive)),
            " ".join(sorted(candidate_distinctive)),
        ),
        "full_sequence": _sequence_score(incoming_name, candidate_name),
        "generic_only_overlap": bool(
            (incoming_all & candidate_all) and not common_distinctive
        ),
    }


def _analysis_result(
    *,
    score: float,
    blockers: list[str],
    evidence: list[str],
    features: dict,
    taxonomy_state: str,
    taxonomy_values: tuple[str, str],
    relation: dict | None = None,
    auto_safe: bool = False,
) -> dict:
    return {
        "score": round(max(0.0, min(float(score), 1.0)), 4),
        "blocked": bool(blockers),
        "blockers": list(dict.fromkeys(blockers)),
        "evidence": list(dict.fromkeys(evidence)),
        "name_features": features,
        "taxonomy_state": taxonomy_state,
        "taxonomy_values": {
            "incoming": taxonomy_values[0],
            "candidate": taxonomy_values[1],
        },
        "relation": relation,
        "auto_safe": bool(auto_safe and not blockers),
    }


def name_similarity(first: Any, second: Any) -> float:
    """Conservative lexical similarity retained for display/diagnostics.

    Entity matching does not rely on this value alone. It is intentionally
    capped when names share no exact token, preventing character-length or
    spelling coincidences from being interpreted as identity.
    """
    first_normalized = normalize_match_name(first)
    second_normalized = normalize_match_name(second)
    if not first_normalized or not second_normalized:
        return 0.0
    if first_normalized == second_normalized:
        return 1.0
    first_tokens = set(name_tokens(first))
    second_tokens = set(name_tokens(second))
    common = first_tokens & second_tokens
    direct = _sequence_score(first_normalized, second_normalized)
    if not common:
        return round(min(direct * 0.45, 0.49), 4)
    score = (
        0.40 * direct
        + 0.35 * _jaccard(first_tokens, second_tokens)
        + 0.25 * _containment(first_tokens, second_tokens)
    )
    return round(min(score, 0.97), 4)


def product_candidate_analysis(incoming: dict, candidate: dict) -> dict:
    features = _name_features(incoming, candidate, "product")
    blockers: list[str] = []
    evidence: list[str] = []
    score = 0.0

    incoming_sku = _clean_identifier(incoming.get("sku"))
    candidate_sku = _clean_identifier(candidate.get("sku"))
    sku_exact = bool(incoming_sku and incoming_sku == candidate_sku)
    if incoming_sku and candidate_sku and not sku_exact:
        blockers.append("sku_different")
    elif sku_exact:
        evidence.append("sku_exact")
        score += 0.62

    incoming_supplier = str(incoming.get("supplier_id") or "").strip()
    candidate_supplier = str(candidate.get("supplier_id") or "").strip()
    if incoming_supplier and candidate_supplier:
        if incoming_supplier != candidate_supplier:
            blockers.append("supplier_different")
        else:
            evidence.append("supplier_same")
            score += 0.10

    taxonomy_state, tax_first, tax_second = _taxonomy_state(
        incoming, candidate, "product"
    )
    if taxonomy_state == "different":
        blockers.append("taxonomy_incompatible")
    elif taxonomy_state == "same":
        evidence.append("taxonomy_same")
        score += 0.14

    if features["exact_name"]:
        evidence.append("name_exact")
        score += 0.62
    elif features["common_distinctive"]:
        evidence.append("distinctive_words_exact")
        score += 0.46 * features["distinctive_containment"]
        score += 0.10 * features["distinctive_jaccard"]
        score += 0.08 * features["distinctive_sequence"]
    elif not sku_exact:
        blockers.append("no_distinctive_word_in_common")

    if features["generic_only_overlap"]:
        blockers.append("only_generic_words_in_common")

    score += 0.06 * features["full_sequence"]
    auto_safe = bool(
        (sku_exact or features["exact_name"])
        and taxonomy_state != "different"
        and not blockers
        and (not incoming_supplier or not candidate_supplier or incoming_supplier == candidate_supplier)
    )
    return _analysis_result(
        score=score,
        blockers=blockers,
        evidence=evidence,
        features=features,
        taxonomy_state=taxonomy_state,
        taxonomy_values=(tax_first, tax_second),
        auto_safe=auto_safe,
    )


def activation_candidate_analysis(incoming: dict, candidate: dict) -> dict:
    features = _name_features(incoming, candidate, "activation")
    blockers: list[str] = []
    evidence: list[str] = []
    score = 0.0

    incoming_supplier = str(incoming.get("supplier_id") or "").strip()
    candidate_supplier = str(candidate.get("supplier_id") or "").strip()
    if incoming_supplier and candidate_supplier:
        if incoming_supplier != candidate_supplier:
            blockers.append("supplier_different")
        else:
            evidence.append("supplier_same")
            score += 0.10

    incoming_project = normalize_match_name(incoming.get("project_name"))
    candidate_project = normalize_match_name(candidate.get("project_name"))
    if incoming_project and candidate_project:
        if incoming_project != candidate_project:
            blockers.append("project_different")
        else:
            evidence.append("project_same")
            score += 0.18

    taxonomy_state, tax_first, tax_second = _taxonomy_state(
        incoming, candidate, "activation"
    )
    if taxonomy_state == "different":
        blockers.append("taxonomy_incompatible")
    elif taxonomy_state == "same":
        evidence.append("taxonomy_same")
        score += 0.12

    if features["exact_name"]:
        evidence.append("name_exact")
        score += 0.64
    elif features["common_distinctive"]:
        evidence.append("distinctive_words_exact")
        score += 0.48 * features["distinctive_containment"]
        score += 0.10 * features["distinctive_jaccard"]
        score += 0.08 * features["distinctive_sequence"]
    else:
        blockers.append("no_distinctive_word_in_common")

    if features["generic_only_overlap"]:
        blockers.append("only_generic_words_in_common")

    score += 0.06 * features["full_sequence"]
    auto_safe = bool(
        features["exact_name"]
        and taxonomy_state != "different"
        and not blockers
        and (not incoming_project or not candidate_project or incoming_project == candidate_project)
    )
    return _analysis_result(
        score=score,
        blockers=blockers,
        evidence=evidence,
        features=features,
        taxonomy_state=taxonomy_state,
        taxonomy_values=(tax_first, tax_second),
        auto_safe=auto_safe,
    )


def _venue_hierarchy_relation(incoming: dict, candidate: dict, features: dict) -> dict | None:
    incoming_tokens = set(name_tokens(incoming.get("name")))
    candidate_tokens = set(name_tokens(candidate.get("name")))
    if not incoming_tokens or not candidate_tokens or incoming_tokens == candidate_tokens:
        return None

    incoming_domain = _domain(incoming.get("website_url"))
    candidate_domain = _domain(candidate.get("website_url"))
    incoming_address = _normalized_address(incoming.get("address"))
    candidate_address = _normalized_address(candidate.get("address"))
    incoming_postal = _clean_identifier(incoming.get("postal_code"))
    candidate_postal = _clean_identifier(candidate.get("postal_code"))
    same_location_signal = bool(
        (incoming_domain and incoming_domain == candidate_domain)
        or (incoming_address and incoming_address == candidate_address)
        or (incoming_postal and incoming_postal == candidate_postal)
        or (
            _same_or_blank(incoming.get("city"), candidate.get("city"))
            and _same_or_blank(incoming.get("state"), candidate.get("state"))
            and str(incoming.get("operator_id") or "")
            and str(incoming.get("operator_id") or "")
            == str(candidate.get("operator_id") or "")
        )
    )
    if not same_location_signal:
        return None

    if candidate_tokens < incoming_tokens:
        extra = incoming_tokens - candidate_tokens
        if extra and all(token in SUBSPACE_TOKENS or token.isdigit() for token in extra):
            return {
                "type": "parent_subspace",
                "incoming_role": "subspace",
                "parent_candidate_id": candidate.get("id"),
                "subspace_tokens": sorted(extra),
            }
    if incoming_tokens < candidate_tokens:
        extra = candidate_tokens - incoming_tokens
        if extra and all(token in SUBSPACE_TOKENS or token.isdigit() for token in extra):
            return {
                "type": "parent_subspace",
                "incoming_role": "parent",
                "child_candidate_id": candidate.get("id"),
                "subspace_tokens": sorted(extra),
            }
    return None


def venue_candidate_analysis(incoming: dict, candidate: dict) -> dict:
    features = _name_features(incoming, candidate, "venue")
    hierarchy = _venue_hierarchy_relation(incoming, candidate, features)
    if hierarchy and hierarchy.get("incoming_role") == "subspace":
        taxonomy_state, tax_first, tax_second = _taxonomy_state(
            incoming, candidate, "venue"
        )
        return _analysis_result(
            score=0.96,
            blockers=[],
            evidence=["parent_name_exact", "location_identifier_same"],
            features=features,
            taxonomy_state=taxonomy_state,
            taxonomy_values=(tax_first, tax_second),
            relation=hierarchy,
            auto_safe=False,
        )

    blockers: list[str] = []
    evidence: list[str] = []
    score = 0.0

    if not _same_or_blank(incoming.get("city"), candidate.get("city")):
        blockers.append("city_different")
    if not _same_or_blank(incoming.get("state"), candidate.get("state")):
        blockers.append("state_different")

    incoming_domain = _domain(incoming.get("website_url"))
    candidate_domain = _domain(candidate.get("website_url"))
    domain_exact = bool(incoming_domain and incoming_domain == candidate_domain)
    if domain_exact:
        evidence.append("website_domain_same")
        score += 0.34

    incoming_address = _normalized_address(incoming.get("address"))
    candidate_address = _normalized_address(candidate.get("address"))
    address_exact = bool(incoming_address and incoming_address == candidate_address)
    if address_exact:
        evidence.append("address_same")
        score += 0.34

    incoming_postal = _clean_identifier(incoming.get("postal_code"))
    candidate_postal = _clean_identifier(candidate.get("postal_code"))
    postal_exact = bool(incoming_postal and incoming_postal == candidate_postal)
    if postal_exact:
        evidence.append("postal_code_same")
        score += 0.20

    incoming_operator = str(incoming.get("operator_id") or "").strip()
    candidate_operator = str(candidate.get("operator_id") or "").strip()
    if incoming_operator and candidate_operator:
        if incoming_operator == candidate_operator:
            evidence.append("operator_same")
            score += 0.10
        elif not (domain_exact or address_exact):
            blockers.append("operator_different")

    taxonomy_state, tax_first, tax_second = _taxonomy_state(
        incoming, candidate, "venue"
    )
    if taxonomy_state == "different" and not (domain_exact or address_exact):
        blockers.append("taxonomy_incompatible")
    elif taxonomy_state == "same":
        evidence.append("taxonomy_same")
        score += 0.10

    if features["exact_name"]:
        evidence.append("name_exact")
        score += 0.58
    elif features["common_distinctive"]:
        evidence.append("distinctive_words_exact")
        score += 0.44 * features["distinctive_containment"]
        score += 0.10 * features["distinctive_jaccard"]
        score += 0.06 * features["distinctive_sequence"]
    elif not (domain_exact or address_exact or postal_exact):
        blockers.append("no_distinctive_word_or_identifier_in_common")

    if features["generic_only_overlap"] and not (
        domain_exact or address_exact or postal_exact
    ):
        blockers.append("only_generic_words_in_common")

    # Two different official domains are a strong contradiction unless name
    # and physical address both confirm the same entity.
    if (
        incoming_domain and candidate_domain and incoming_domain != candidate_domain
        and not (features["exact_name"] and address_exact)
    ):
        blockers.append("official_domains_different")

    score += 0.05 * features["full_sequence"]
    auto_safe = bool(
        features["exact_name"]
        and not blockers
        and (domain_exact or address_exact or postal_exact or incoming_operator == candidate_operator)
    )
    return _analysis_result(
        score=score,
        blockers=blockers,
        evidence=evidence,
        features=features,
        taxonomy_state=taxonomy_state,
        taxonomy_values=(tax_first, tax_second),
        relation=hierarchy,
        auto_safe=auto_safe,
    )


def product_candidate_score(incoming: dict, candidate: dict) -> float:
    analysis = product_candidate_analysis(incoming, candidate)
    return 0.0 if analysis["blocked"] else float(analysis["score"])


def activation_candidate_score(incoming: dict, candidate: dict) -> float:
    analysis = activation_candidate_analysis(incoming, candidate)
    return 0.0 if analysis["blocked"] else float(analysis["score"])


def venue_candidate_score(incoming: dict, candidate: dict) -> float:
    analysis = venue_candidate_analysis(incoming, candidate)
    return 0.0 if analysis["blocked"] else float(analysis["score"])


MATCH_CONFIG = {
    "product": {
        "auto_threshold": 0.96,
        "review_threshold": 0.68,
        "score_function": product_candidate_score,
        "analysis_function": product_candidate_analysis,
    },
    "activation": {
        "auto_threshold": 0.96,
        "review_threshold": 0.70,
        "score_function": activation_candidate_score,
        "analysis_function": activation_candidate_analysis,
    },
    "venue": {
        "auto_threshold": 0.94,
        "review_threshold": 0.72,
        "score_function": venue_candidate_score,
        "analysis_function": venue_candidate_analysis,
    },
}


def analyze_candidate_pair(entity_type: str, incoming: dict, candidate: dict) -> dict:
    return MATCH_CONFIG[entity_type]["analysis_function"](incoming, candidate)


def best_candidate_match(entity_type: str, incoming: dict, candidates: list[dict]) -> dict:
    config = MATCH_CONFIG[entity_type]
    ranked: list[dict] = []

    for candidate in candidates:
        analysis = config["analysis_function"](incoming, candidate)
        relation = analysis.get("relation") or {}
        if relation.get("type") == "parent_subspace" and relation.get("incoming_role") == "subspace":
            ranked.append({
                "candidate": candidate,
                "score": float(analysis["score"]),
                "analysis": analysis,
                "hierarchy": True,
            })
            continue
        if analysis.get("blocked") or float(analysis.get("score") or 0) <= 0:
            continue
        ranked.append({
            "candidate": candidate,
            "score": float(analysis["score"]),
            "analysis": analysis,
            "hierarchy": False,
        })

    if not ranked:
        return {
            "decision": "none", "candidate": None, "score": 0.0,
            "method": "no_safe_candidate", "analysis": None,
        }

    ranked.sort(key=lambda item: item["score"], reverse=True)
    best = ranked[0]
    second_score = ranked[1]["score"] if len(ranked) > 1 else 0.0
    score = float(best["score"])
    margin = score - second_score
    analysis = best["analysis"]

    if best.get("hierarchy"):
        return {
            "decision": "hierarchy",
            "candidate": best["candidate"],
            "score": score,
            "method": "parent_subspace_relation",
            "analysis": analysis,
            "relation": analysis.get("relation"),
        }

    if analysis.get("auto_safe") and score >= config["auto_threshold"] and margin >= 0.02:
        return {
            "decision": "auto", "candidate": best["candidate"],
            "score": score, "method": "identifiers_and_taxonomy",
            "analysis": analysis,
        }

    strong_evidence = {
        "sku_exact", "name_exact", "distinctive_words_exact",
        "website_domain_same", "address_same", "postal_code_same",
    } & set(analysis.get("evidence") or [])
    if score >= config["review_threshold"] and strong_evidence:
        return {
            "decision": "review", "candidate": best["candidate"],
            "score": score, "method": "distinctive_taxonomy_identifier_review",
            "analysis": analysis,
        }

    return {
        "decision": "none", "candidate": None, "score": score,
        "method": "insufficient_identity_evidence", "analysis": analysis,
    }
